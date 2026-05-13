# Skill: /kltn-implement (FE)

## Kích hoạt
`/kltn-implement [issue-number]` — làm việc trên GitHub Issue phía Frontend (Web hoặc Mobile).

---

## Quy trình

### Bước 0 — Kiểm tra CLAUDE.local.md
```bash
cat .claude/CLAUDE.local.md 2>/dev/null || { echo "❌ CLAUDE.local.md chưa tồn tại — tạo file này trước (xem /kltn-setup)"; exit 1; }
```
Xác nhận file có đủ 4 trường: **Tên**, **MSSV**, **Role chính**, **Role phụ**.
Nếu thiếu → dừng lại và yêu cầu tạo/bổ sung trước khi tiếp tục.

### Bước 1 — Đọc GitHub Issue
```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels,milestone,assignees
```
Từ output ghi nhớ:
- `$ISSUE_NUMBER` — số issue (ví dụ: `12`)
- `$ISSUE_TITLE` — title của issue
- `$SPRINT` — milestone name
- **Web** (ReactJS) hay **Mobile** (React Native / Expo)?
- Output mong đợi là gì? (màn hình, component, API call nào?)
- Có dependency với issue BE nào không?

### Bước 2 — Lập Implementation Plan & viết plan.md

Phân tích issue và viết file plan tại `logs/GH-$ISSUE_NUMBER/plan.md`:

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING
- **Role:** FE | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [GitHub URL]
- **Sprint:** [milestone]

## Mục tiêu
[Issue yêu cầu làm gì, output là gì]

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| path/to/file.tsx | create/modify | ... |

## Approach
[Cấu trúc component, state management, API calls]

## Steps
- [ ] Bước 1: [...]
- [ ] Bước 2: [...]
- [ ] Bước 3: [...]
```

> **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi làm bất cứ bước nào tiếp theo.**
> **TUYỆT ĐỐI KHÔNG CODE khi chưa có xác nhận. Không có ngoại lệ, dù issue nhỏ đến đâu.**

### Bước 2.5 — Chọn executor

Sau khi plan được approve, hỏi user:

> **"Ai sẽ thực thi plan này?"**
> 1. **Claude** — Claude Code tự implement (tiếp tục Bước 3 bên dưới)
> 2. **Codex** — Trigger Codex CLI thực thi plan (Claude dừng lại sau bước này)

**Nếu user chọn Option 2 — Codex:**
```bash
codex "Execute the implementation plan in logs/GH-$ISSUE_NUMBER/plan.md.
Follow the coding conventions in .codex/skills/fe/ for all patterns (feature folder, TanStack Query hooks, service layer, Zod schemas).
Branch: feature/GH-$ISSUE_NUMBER-$(gh issue view $ISSUE_NUMBER --json title -q '.title' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-30)
Do not commit or push — stop after implementation."
```

Claude dừng lại sau khi chạy lệnh trên. Codex sẽ tự đọc plan và thực thi.

**Nếu user chọn Option 1 — Claude:** tiếp tục Bước 3 bên dưới.

---

### Bước 3 — Tạo branch
```bash
git checkout -b feature/GH-$ISSUE_NUMBER-ten-tinh-nang
```

### Bước 4 — Implement theo đúng cấu trúc

**Web (ReactJS) — Feature-based + Shared:**
```
src/
├── config/
│   └── env.ts                   ← Zod-validate import.meta.env khi boot
├── router/
│   ├── index.tsx                ← createBrowserRouter — toàn bộ route tree
│   ├── ProtectedRoute.tsx       ← redirect /login nếu chưa auth
│   └── RoleRoute.tsx            ← redirect /unauthorized nếu sai role
├── features/<tên-feature>/
│   ├── pages/                   ← route entry: layout + gọi hook, không có logic
│   ├── components/              ← UI components của feature này
│   ├── hooks/                   ← useQuery / useMutation (TanStack Query)
│   ├── services/                ← Axios API calls qua axiosInstance
│   ├── schemas/                 ← Zod schema cho form validation
│   └── types/                   ← TypeScript types của feature
└── shared/
    ├── components/
    │   ├── layout/              ← AppLayout, AuthLayout, Sidebar, Header
    │   ├── common/              ← LoadingSpinner, ErrorBoundary, EmptyState
    │   └── ui/                  ← shadcn generated components
    ├── context/
    │   └── authContext.tsx      ← AuthProvider: hydrate sessionStore từ cookie khi boot
    ├── lib/
    │   ├── axios.ts             ← Axios instance + interceptors (không tạo instance mới)
    │   └── errors.ts            ← HttpError, EntityError, handleErrorApi
    ├── utils/
    │   └── queryKeys.ts         ← KEY (root) + QUERY_KEY (factories)
    ├── stores/
    │   └── sessionStore.ts      ← Zustand: token, user, setToken, logout
    └── types/
        ├── api.types.ts         ← ResponseData<T>, PaginationResponse<T>, ErrorEntity
        └── common.types.ts      ← BaseFilterPagination, shared query types
```

**Không đặt file mới vào `shared/` trừ khi dùng ở ≥ 2 feature khác nhau.**

**shadcn/ui (Web):**
- UI primitive dùng từ `shared/components/ui`.
- Nếu cần primitive mới: chạy `npx shadcn@latest add <component>`.
- Không tự viết lại Button/Input/Form/Dialog/Table/Badge/Skeleton nếu shadcn đã có.

**Mobile (React Native / Expo):**
```
app/            ← Expo Router screens
components/     ← UI components
stores/         ← Zustand global state
services/       ← Axios API calls
```

### Bước 5 — Tự kiểm tra trước commit
- Không còn `console.log`
- Loading + error state đã xử lý
- UI primitive import từ `shared/components/ui`, không tự custom lại component shadcn đã có
- Không hardcode URL / token
- Route mới đã khai báo trong `router/index.tsx`
- Page cần auth đã wrap `ProtectedRoute`
- Page có role restriction đã wrap `RoleRoute` (Admin / Manager / Staff)
- Responsive đúng (Web)

> ⛔ **KHÔNG commit, KHÔNG push** trong bước này.
> Commit + push + tạo PR chỉ được thực hiện khi chạy `/kltn-ship $ISSUE_NUMBER`.

---

## Sau khi implement xong — chạy theo thứ tự

```
/kltn-reviewcode  →  /kltn-test  →  /kltn-ship $ISSUE_NUMBER
```

`/kltn-test` với FE sẽ chạy:
```bash
# Web
npx tsc --noEmit                  # type check
npx eslint . --max-warnings=0     # lint (0 warning)
npm run build                     # production build

# Mobile
npx tsc --noEmit
npx expo lint
```

> Cả 3 bước phải PASS trước khi `/kltn-ship`. Không bỏ qua TypeScript error hay ESLint warning.

---

## Không được
- Gọi API trực tiếp trong component (phải qua `services/`)
- Đặt state global vào `useState` local nếu nhiều component dùng
- Hardcode URL API (dùng env variable)
- Thêm npm package chưa có trong tech-defaults

---

## Stack FE
**Web:** React 19 · React Router DOM v7 · TanStack Query v5 · Zustand · Axios · React Hook Form + Zod · shadcn/ui · Tailwind v4 · Recharts · Sonner · js-cookie · jwt-decode · next-themes · date-fns
**Mobile:** React Native · Expo · Expo Router · Axios
