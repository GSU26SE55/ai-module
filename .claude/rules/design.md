# Design — Kiến trúc hệ thống

## Tổng quan

3 layer độc lập, giao tiếp qua REST API:

```
[Mobile App]  ←→  [Web App]
      ↓               ↓
    [ASP.NET Core Web API]
      ↓               ↓
[PostgreSQL/TimescaleDB]  [Redis Cache]
      ↓
  [AI Module]
```

---

## Layer 1: Backend (ASP.NET Core)

- **Auth:** JWT, role-based (Admin / Manager / Staff / Customer)
- **Battery API:** CRUD pin, lịch sử đo lường, ngưỡng cảnh báo
- **Ticket API:** tạo ticket, cập nhật trạng thái, SLA timer
- **AI Bridge:** gọi AI module để lấy dự đoán SOH + phân loại

**Database design:**
- `PostgreSQL` — dữ liệu relational (users, tickets, battery configs)
- `TimescaleDB` — time-series data (sensor readings theo thời gian)
- `Redis` — cache session, pub/sub cho real-time alert

---

## Layer 2: Frontend (ReactJS)

3 portal theo role:
- **Admin portal** — quản lý user, pin, SLA definition
- **Manager portal** — dashboard tổng quan, báo cáo
- **Staff portal** — ticket queue, maintenance log

### Cấu trúc `src/` — Feature-based + Shared

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
    │   ├── ui/                     ← shadcn components
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
    │   └── sessionStore.ts         ← Zustand: token, user, setToken, logout — nguồn sự thật auth duy nhất
    ├── context/
    │   └── authContext.tsx         ← AuthProvider: hydrate sessionStore từ cookie khi boot
    └── types/
        ├── api.types.ts            ← ResponseData<T>, PaginationResponse<T>, ErrorEntity
        └── common.types.ts         ← BaseFilterPagination, shared query types
```

### Route tree

```
/                     → redirect theo role (Admin/Manager/Staff)
/login                → AuthLayout > LoginPage
/forgot-password      → AuthLayout > ForgotPasswordPage

/admin/*              → ProtectedRoute(role=Admin) > AppLayout
/manager/*            → ProtectedRoute(role=Manager) > AppLayout
/staff/*              → ProtectedRoute(role=Staff) > AppLayout
/unauthorized         → trang 403
```

### Quy tắc bắt buộc FE

- Không gọi API trong component — luôn qua `services/` → hook TanStack Query
- `useState` chỉ cho UI state thuần (modal open/close, tab active)
- Zustand chỉ cho auth session — không dùng làm server state cache
- `features/admin` không import từ `features/manager` — feature độc lập nhau
- `shared/` là nơi duy nhất chứa code tái sử dụng cross-feature
- Không hardcode URL — dùng `env.VITE_API_BASE_URL`

**SLA theo ITIL — Priority-based:**
- P1 (Critical): resolve < 4h — pin mất điện / nguy cơ an toàn. Breach → reassign Senior + notify Admin.
- P2 (High): resolve < 24h — degradation đáng kể / hiệu suất giảm. Breach → Manager reassign.
- P3 (Standard): resolve < 72h — bất thường nhẹ / bảo trì định kỳ. Breach → Manager review.
- Priority do Manager gán khi triage, **không thay đổi** trong vòng đời ticket.
- Breach → escalate thêm nhân lực/cấp bậc, không extend deadline.

---

## Layer 3: Mobile App (React Native/Expo)

- Real-time sensor display (polling hoặc WebSocket)
- Notification push khi có cảnh báo
- Tạo ticket hỗ trợ từ app
- Xem lịch sử + prediction chart

---

## AI Module

**Mục tiêu:** 2 core model (không thêm):
1. **LSTM/CNN-LSTM** — dự đoán SOH (State of Health)
2. **Isolation Forest hoặc Autoencoder** — phát hiện bất thường

**Dataset:** Ưu tiên NASA Ames → CALCE nếu cần thêm data.

**Thực tế capstone:** Target accuracy 85–90%, không overpromise 99%+.

**Output:** Classification (Normal / Degrading / Failed) + SOH % + confidence score
