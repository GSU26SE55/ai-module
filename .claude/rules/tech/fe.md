# Tech — Frontend (Web)

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Framework | React 19 | — |
| Router | React Router DOM v7 | `createBrowserRouter` + nested layouts |
| Server state | TanStack Query v5 | Cache, loading/error tự động |
| Client state | Zustand v5 | Chỉ cho auth session + UI state |
| HTTP | Axios | Interceptors: auto-attach token + refresh |
| Form | React Hook Form + Zod | Validation schema-first |
| UI | shadcn/ui + Tailwind v4 | Generate component source vào `src/shared/components/ui` |
| Charts | Recharts | SLA timeline, battery health |
| Toast | Sonner | Thông báo thành công / lỗi |
| Auth cookie | js-cookie | Đọc/ghi accessToken, refreshToken |
| JWT decode | jwt-decode | Lấy user info + exp từ token |
| Theme | next-themes | Light / dark mode |
| Date | date-fns | Format SLA countdown, audit log |
| Env validate | Zod | Throw ngay khi thiếu biến môi trường |

---

## Cấu trúc `src/` — Feature-based + Shared

```
src/
├── main.tsx
├── App.tsx                         ← providers: QueryClient, AuthProvider, ThemeProvider, Router, Toaster
├── config/
│   └── env.ts                      ← Zod-validate import.meta.env khi boot
├── router/
│   ├── index.tsx                   ← createBrowserRouter — toàn bộ route tree
│   ├── ProtectedRoute.tsx          ← check isHydrating → loader | !auth → /login
│   └── RoleRoute.tsx               ← allowedRoles: UserRole[] | sai role → /unauthorized
├── features/                       ← mỗi feature = 1 domain nghiệp vụ độc lập
│   ├── auth/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/                  ← useMutation (useLogin, useLogout, ...)
│   │   ├── services/               ← auth.service.ts
│   │   ├── schemas/                ← Zod schemas
│   │   └── types/
│   ├── admin/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   ├── manager/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   └── staff/
│       ├── pages/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       └── types/
└── shared/
    ├── components/
    │   ├── ui/                     ← shadcn components (generated — không edit tay)
    │   ├── layout/                 ← AppLayout, AuthLayout, Sidebar, Header
    │   └── common/                 ← LoadingSpinner, ErrorBoundary, EmptyState
    ├── hooks/
    │   └── useDebounce.ts
    ├── lib/
    │   ├── axios.ts                ← Axios instance + interceptors (token attach + refresh queue)
    │   ├── authz.ts                ← RBAC: P constants, checkPermission(), checkRole()
    │   ├── errors.ts               ← HttpError, EntityError, handleErrorApi
    │   └── utils.ts                ← shadcn cn() utility
    ├── stores/
    │   └── sessionStore.ts         ← Zustand: user, setSession, clearSession
    ├── context/
    │   └── authContext.tsx         ← AuthProvider: isHydrating + 3-case boot logic
    ├── utils/
    │   ├── queryKeys.ts            ← KEY (root) + QUERY_KEY (factories)
    │   └── endpoints.ts            ← ENDPOINTS — single source of truth cho API paths
    └── types/
        ├── api.types.ts            ← CommonResponse<T>, PaginationResponse<T>, ErrorEntity
        ├── session.types.ts        ← SessionUser, JwtPayload, UserRole, decodeToken, redirectByRole
        └── common.types.ts         ← BaseFilterPagination, shared query types
```

---

## Route tree

```
/                       → redirect theo role hoặc /login nếu chưa auth
/login                  → AuthLayout > LoginPage
/register               → AuthLayout > RegisterPage
/register/verify-otp    → AuthLayout > OtpVerifyPage  (email từ router state)
/forgot-password        → AuthLayout > ForgotPasswordPage  (multi-step nội bộ)
/auth/google/callback   → GoogleCallbackPage  (không có layout)
/unauthorized           → trang 403

/admin/*                → ProtectedRoute > RoleRoute(['ADMIN']) > AppLayout
/manager/*              → ProtectedRoute > RoleRoute(['MANAGER']) > AppLayout
/staff/*                → ProtectedRoute > RoleRoute(['STAFF']) > AppLayout
```

---

## Naming Conventions

| Type | Pattern | Ví dụ |
|------|---------|-------|
| Page component | `{Name}Page.tsx` | `LoginPage.tsx` |
| Feature component | `{Name}.tsx` (PascalCase) | `BatteryCard.tsx` |
| Hook | `use{Name}.ts` | `useBatteries.ts` |
| Service | `{name}.service.ts` | `battery.service.ts` |
| Zod schema | `{name}.schema.ts` | `login.schema.ts` |
| Type file | `{name}.types.ts` | `battery.types.ts` |

---

## Auth & Session

**UserRole** — luôn UPPERCASE trong toàn app:
```ts
export type UserRole = 'ADMIN' | 'MANAGER' | 'STAFF' | 'CUSTOMER';
```
JWT gửi PascalCase (`"Customer"`) → `.toUpperCase()` khi decode, không normalize ở chỗ khác.

**SessionUser** — shape lưu vào Zustand sau khi decode JWT:
```ts
interface SessionUser {
  accountId: string;     // ← JWT.AccountId
  email: string;
  fullName: string;      // ← JWT.FullName
  role: UserRole;
  permissions: string[]; // ← JWT.perm[]
}
```

**File vị trí bắt buộc** — `src/shared/types/session.types.ts` chứa: `UserRole`, `SessionUser`, `JwtPayload`, `decodeToken`, `redirectByRole`.
KHÔNG đặt ở `features/auth/` — gây circular: `shared/lib/axios.ts → features/auth/ → shared/lib/axios.ts`.

**Session hydration (AuthContext boot)** — 3 cases:
```
Case 1: accessToken còn hạn  → decode → setSession → isHydrating = false ✅
Case 2: không có refreshToken → logout() → isHydrating = false → /login
Case 3: accessToken hết hạn, có refreshToken → POST refresh
          → OK:   saveTokens → decode → setSession → isHydrating = false ✅
          → fail: logout() → isHydrating = false → /login
```
`ProtectedRoute` PHẢI check `isHydrating` trước khi redirect — render `<PageLoader />` khi đang hydrate.

**Token storage** — `js-cookie` only:
- `accessToken`: expires = `exp` từ JWT
- `refreshToken`: expires = 7 ngày
- Không dùng `localStorage` cho token

**Logout** — 2 context:
- Trong React tree: `Cookies.remove(...)` + `sessionStore.clearSession()` + `navigate('/login')`
- Trong Axios interceptor (ngoài React tree): `window.location.href = '/login'`

**CUSTOMER login vào web** — block sớm trong `useLogin onSuccess`: toast error + logout().

---

## Axios Interceptor — Token Refresh

**Request flow:**
```
isTokenExpired(accessToken)?
  false → attach Bearer → gửi
  true  → tryRefresh() → OK: attach token mới | fail: logout()

Response 401 → tryRefresh() nếu chưa refresh lần này
  → OK: retry | fail: logout() + window.location.href = '/login'
```

**Chống double-refresh:** `isRefreshing` flag + `pendingQueue`. Refresh call timeout 10s. `finally` reset flag + flush queue — không được đảo thứ tự flush và reset.

---

## RBAC — `src/shared/lib/authz.ts`

Backend gửi `perm[]` trong JWT — FE không cần static matrix. `P` constants là type-safe string reference.

```ts
checkPermission(user, P.TICKET_ASSIGN)   // feature-level gate (ẩn/hiện button)
checkRole(user, 'ADMIN', 'MANAGER')      // layout-level gate (menu, RoleRoute)
```

- Component luôn dùng `P.XXX`, không hardcode string `'ticket.assign'`
- `P` constants chỉ mở rộng khi có feature mới — không define speculative permissions

---

## ENDPOINTS — `src/shared/utils/endpoints.ts`

Single source of truth cho toàn bộ API path. Quy tắc:
- Service files import từ `ENDPOINTS` — không hardcode string URL
- Thêm endpoint mới → thêm vào `endpoints.ts` trước, rồi mới dùng trong service
- `features/` không import `ENDPOINTS` trực tiếp — chỉ qua `services/`

```ts
// Pattern cho static và dynamic endpoint:
AUTH: { LOGIN: '/api/auth/login' }
BATTERIES: { DETAIL: (id: string) => `/api/batteries/${id}` }
```

---

## TanStack Query — Cache Strategy

**QueryClient defaults** (`App.tsx`):
```ts
staleTime: 2 phút | gcTime: 10 phút | retry: 1 | refetchOnWindowFocus: false
```

**Override per-query:**

| Data type | staleTime | refetchInterval |
|-----------|-----------|-----------------|
| Ticket queue | 30s | — |
| SLA countdown | 0 | 30s |
| Battery config | 10 phút | — |
| Dashboard stats | 1 phút | — |
| User list | 5 phút | — |

> `staleTime: 0` không tự refetch — phải kết hợp `refetchInterval` để auto-refetch thực sự.
> `refetchInterval` tự dừng khi query ở `status: 'error'`.

**Query Key Convention** — `shared/utils/queryKeys.ts`:
```ts
KEY.batteries                           // root — dùng để invalidate broad
QUERY_KEY.batteries.list(params)        // factory — dùng trong useQuery
QUERY_KEY.batteries.detail(id)          // factory — dùng trong useQuery
```

---

## Error Handling

**Lớp lỗi** (`shared/lib/errors.ts`):
- `HttpError` — lỗi chung (statusCode + message) → hiện toast
- `EntityError extends HttpError` — lỗi validation field từ BE (`listErrors`) → map xuống input

**Rule phân biệt 2 dạng:**

| Dạng | Pattern | Hiển thị lỗi |
|------|---------|--------------|
| **Có form** (React Hook Form) | `mutateAsync` trong `try-catch` + `handleErrorApi({ error, setError })` | `EntityError` → lỗi dưới từng input field; `HttpError` → toast |
| **Không có form** (delete, approve, cancel...) | `onError` của `useMutation` + `handleErrorApi({ error })` | Toast trực tiếp |

**Form submit — bắt buộc dùng `try-catch` + `setError`:**
```ts
const { handleSubmit, setError } = useForm<LoginPayload>();
const { mutateAsync } = useLogin();

const onSubmit = async (data: LoginPayload) => {
  try {
    await mutateAsync(data);
  } catch (error) {
    handleErrorApi({ error, setError });
    // EntityError → setError('email', ...), setError('password', ...) — hiện dưới input
    // HttpError  → toast.error(message)
  }
};
```

**Non-form — dùng `onError` của mutation:**
```ts
const { mutate } = useMutation({
  mutationFn: (id: string) => batteryService.delete(id),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: KEY.batteries });
    toast.success('Đã xóa');
  },
  onError: (error) => handleErrorApi({ error }),  // toast trực tiếp, không có setError
});
```

> **KHÔNG** dùng `onError` cho form submit — `onError` không nhận `setError` nên không map được lỗi xuống input field.

---

## Feature Isolation

`no-restricted-imports` trong `eslint.config.js` — block cross-feature import tự động.
CI fail nếu `features/admin` import từ `features/manager` hoặc `features/staff` (và ngược lại).

---

## Template Plan — FE

Plan cho ticket FE **bắt buộc** có đủ các section sau. Thiếu bất kỳ section nào → plan chưa đủ, không được approve.

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING | **Role:** FE | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [URL]
- **Sprint:** Sprint N (deadline YYYY-MM-DD)

## Mục tiêu
[Mô tả ngắn gọn — issue này làm gì, tại sao cần]

## Scope
**Trong scope:** [liệt kê]
**Ngoài scope:** [liệt kê — tránh scope creep]

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/features/auth/types/auth.types.ts` | create | LoginPayload, AuthUser |
| `src/features/auth/hooks/useLogin.ts` | create | useMutation |

## Types
[Liệt kê types/interfaces sẽ tạo — tên + shape ngắn gọn]
```ts
interface LoginPayload { email: string; password: string; }
interface AuthUser { accountId: string; role: UserRole; }
```

## Schema (Zod)
[Liệt kê schemas cho form — field + validation rule]
```ts
// login.schema.ts
email:    z.string().email()
password: z.string().min(8)
```

## Endpoints
| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| POST | `/api/auth/login` | `{ email, password }` | `CommonResponse<{ accessToken, refreshToken }>` |

## Workflow
[Luồng xử lý từ user action đến UI feedback — mỗi flow 1 block]

**Login flow:**
  Submit form → useLogin.mutateAsync(data)
  → OK:   saveTokens → decodeToken → setSession → navigate(redirectByRole(role))
  → FAIL: handleErrorApi({ error, setError }) → lỗi hiện dưới input

## Steps
- [ ] Bước 1: Tạo types + schemas
- [ ] Bước 2: Tạo service
- [ ] Bước 3: Tạo hooks
- [ ] Bước 4: Tạo components + pages
- [ ] Bước 5: Wire vào router
- [ ] Bước 6: `tsc --noEmit` + `eslint --max-warnings=0` + `npm run build` → PASS
```

---

## Nguyên tắc

- Không gọi API trong component — luôn qua `services/` → hook TanStack Query
- `useState` chỉ cho UI state thuần (modal, tab)
- Zustand chỉ cho auth session — không dùng làm server state cache
- `shared/` là nơi duy nhất chứa code tái sử dụng cross-feature
- Không tạo Axios instance mới — dùng `shared/lib/axios.ts`
- Không dùng `localStorage` cho token — chỉ dùng cookie qua `js-cookie`
- Không thêm package mới nếu stack hiện tại đủ — hỏi Leader trước

**Simplicity First:** Chỉ tạo component/hook/service mà issue yêu cầu — không extract abstraction sớm.

**Surgical Changes:** Chỉ sửa files trong plan.md. Không refactor component lân cận ngoài scope task.
