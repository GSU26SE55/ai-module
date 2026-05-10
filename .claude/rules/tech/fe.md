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
| Auth cookie | js-cookie | Đọc/ghi accesstoken, refreshtoken |
| JWT decode | jwt-decode | Lấy user info + exp từ token |
| Theme | next-themes | Light / dark mode |
| Date | date-fns | Format SLA countdown, audit log |
| Env validate | Zod | Throw ngay khi thiếu biến môi trường |

## Packages cần cài (ngoài Vite default)

```bash
npm install zod react-hook-form @hookform/resolvers sonner js-cookie jwt-decode next-themes recharts date-fns
npm install -D @types/js-cookie

# shadcn/ui setup
npx shadcn@latest init
npx shadcn@latest add button input label form card dialog dropdown-menu table badge avatar separator sheet skeleton
```

---

## Cấu trúc `src/` — Feature-based + Shared

```
src/
├── main.tsx                        ← render <App />
├── App.tsx                         ← providers: QueryClient, AuthProvider, ThemeProvider, Router, Toaster
├── config/
│   └── env.ts                      ← Zod-validate import.meta.env khi boot
│
├── router/
│   ├── index.tsx                   ← createBrowserRouter — toàn bộ route tree
│   ├── ProtectedRoute.tsx          ← redirect /login nếu chưa auth
│   └── RoleRoute.tsx               ← redirect /unauthorized nếu sai role
│
├── features/                       ← mỗi feature = 1 domain nghiệp vụ độc lập
│   ├── auth/
│   │   ├── pages/                  ← LoginPage, ForgotPasswordPage
│   │   ├── components/             ← LoginForm, ForgotPasswordForm
│   │   ├── hooks/                  ← useLogin, useLogout (TanStack Query mutations)
│   │   ├── services/               ← auth.service.ts — gọi API qua axiosInstance
│   │   ├── schemas/                ← Zod schemas cho form
│   │   └── types/                  ← LoginPayload, AuthUser
│   ├── admin/
│   │   ├── pages/                  ← UserManagementPage, BatteryConfigPage, SLARulesPage, AuditLogPage
│   │   ├── components/             ← users/, batteries/, sla/
│   │   ├── hooks/                  ← useUsers, useBatteries, useSLARules
│   │   ├── services/               ← user.service.ts, battery.service.ts, sla.service.ts
│   │   └── types/
│   ├── manager/
│   │   ├── pages/                  ← DashboardPage, TicketQueuePage, TicketDetailPage, ReportsPage
│   │   ├── components/             ← tickets/, dashboard/, reports/
│   │   ├── hooks/                  ← useTickets, useDashboard
│   │   ├── services/               ← ticket.service.ts
│   │   └── types/
│   └── staff/
│       ├── pages/                  ← MyTicketsPage, TicketWorkPage
│       ├── components/             ← tickets/, maintenance/
│       ├── hooks/                  ← useMyTickets
│       ├── services/               ← staff-ticket.service.ts
│       └── types/
│
└── shared/                         ← code tái sử dụng across features
    ├── components/
    │   ├── ui/                     ← shadcn components (generated source)
    │   ├── layout/
    │   │   ├── AppLayout.tsx       ← sidebar + header + <Outlet /> (admin/manager/staff)
    │   │   ├── AuthLayout.tsx      ← centered card (login/forgot-password)
    │   │   ├── Sidebar.tsx         ← nav links render theo role
    │   │   └── Header.tsx          ← avatar, notification bell, logout
    │   └── common/                 ← LoadingSpinner, ErrorBoundary, EmptyState
    ├── hooks/
    │   └── useDebounce.ts
    ├── lib/
    │   ├── axios.ts                ← Axios instance + interceptors (token attach + refresh)
    │   └── utils.ts                ← shadcn cn() utility
    ├── stores/
    │   └── sessionStore.ts         ← Zustand: token, user, setToken, logout
    ├── context/
    │   └── authContext.tsx         ← AuthProvider: hydrate sessionStore từ cookie khi boot
    └── types/
        ├── api.types.ts            ← ResponseData<T>, PaginationResponse<T>, ErrorEntity
        └── common.types.ts         ← BaseFilterPagination, shared query types
```

---

## Route tree

```
/                     → redirect theo role (Admin/Manager/Staff)
/login                → AuthLayout > LoginPage
/forgot-password      → AuthLayout > ForgotPasswordPage

/admin/*              → ProtectedRoute(role=Admin) > AppLayout
/manager/*            → ProtectedRoute(role=Manager) > AppLayout
/staff/*              → ProtectedRoute(role=Staff) > AppLayout
/unauthorized         → trang 403
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

## TanStack Query — Cache Strategy

Cấu hình `QueryClient` mặc định trong `App.tsx`:

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2,   // 2 phút — data cũ sau 2 phút, tự refetch
      gcTime:    1000 * 60 * 10,  // 10 phút — xóa khỏi cache sau 10 phút inactive
      retry: 1,                   // retry 1 lần nếu lỗi network
      refetchOnWindowFocus: false, // tắt refetch khi tab active lại (tránh request thừa)
    },
  },
});
```

Override per-query khi cần:

| Data type | staleTime | refetchInterval | Lý do |
|-----------|-----------|-----------------|-------|
| Ticket queue (manager) | `30_000` (30s) | — | Thay đổi thường xuyên |
| SLA countdown | `0` | `30_000` (30s) | Đồng bộ deadline từ server mỗi 30s |
| Battery config | `1000 * 60 * 10` (10 phút) | — | Ít thay đổi |
| Dashboard stats | `1000 * 60` (1 phút) | — | Balanced |
| User list (admin) | `1000 * 60 * 5` (5 phút) | — | Ít thay đổi |

```tsx
// Ticket queue — refetch 30s
const { data: tickets } = useQuery({
  queryKey: ['tickets', filters],
  queryFn: () => ticketService.getList(filters),
  staleTime: 30_000,
});

// SLA countdown — pattern đúng
// staleTime: 0 + refetchInterval: 30s đảm bảo deadline được đồng bộ từ server mỗi 30s.
// setInterval dùng để update UI countdown (hiển thị giây đếm ngược) giữa các lần refetch.
const { data: ticket } = useQuery({
  queryKey: ['ticket', id],
  queryFn: () => ticketService.getById(id),
  staleTime: 0,
  refetchInterval: 30_000,  // ← quan trọng: không có cái này, TanStack Query không tự refetch
});

// Local countdown display — đếm ngược từ deadline server
const [remaining, setRemaining] = useState<number>(0);
useEffect(() => {
  if (!ticket?.slaDeadline) return;
  const update = () => setRemaining(new Date(ticket.slaDeadline).getTime() - Date.now());
  update();
  const id = setInterval(update, 1000);
  return () => clearInterval(id);
}, [ticket?.slaDeadline]);
```

> **Lưu ý:** `staleTime: 0` không tự refetch theo interval — chỉ đánh dấu data là stale ngay khi fetch. Phải dùng `refetchInterval` để có auto-refetch thực sự. `setInterval` chỉ dùng cho UI countdown (giây đếm ngược) dựa trên deadline đã lấy từ server.

---

## Feature Isolation — ESLint Enforcement

Rule `no-restricted-imports` trong `eslint.config.js` để tự động block import chéo giữa features:

```js
// eslint.config.js
import noRestrictedImports from 'eslint-plugin-no-relative-import-paths';

export default [
  {
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [
          // admin KHÔNG import từ manager/staff
          { group: ['*/features/manager/*'], message: 'admin cannot import from manager feature' },
          { group: ['*/features/staff/*'],   message: 'admin cannot import from staff feature' },
          // manager KHÔNG import từ admin/staff
          { group: ['*/features/admin/*'],   message: 'manager cannot import from admin feature' },
          { group: ['*/features/staff/*'],   message: 'manager cannot import from staff feature' },
          // staff KHÔNG import từ admin/manager
          { group: ['*/features/admin/*'],   message: 'staff cannot import from admin feature' },
          { group: ['*/features/manager/*'], message: 'staff cannot import from manager feature' },
        ],
      }],
    },
  },
];
```

> CI chạy `npx eslint . --max-warnings=0` — sẽ FAIL build nếu có cross-feature import.

---

## Nguyên tắc

- Không gọi API trong component — luôn qua `services/` → hook TanStack Query
- `useState` chỉ cho UI state thuần (modal open/close, tab active)
- Zustand chỉ cho auth session — không dùng làm server state cache
- `features/admin` không import từ `features/manager` — feature độc lập nhau (ESLint enforce)
- `shared/` là nơi duy nhất chứa code tái sử dụng cross-feature
- Không hardcode URL — dùng `env.VITE_API_BASE_URL`
- Không tạo Axios instance mới — dùng `shared/lib/axios.ts`
- Không dùng `localStorage` để lưu token — chỉ dùng cookie qua `js-cookie`
- Không thêm package mới nếu stack hiện tại đủ giải quyết — hỏi Leader trước
