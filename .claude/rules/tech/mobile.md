# Tech — Mobile (React Native / Expo)

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Framework | React Native (Expo SDK 51+) | Managed workflow — không eject |
| Navigation | Expo Router v3 | File-based routing |
| Server state | TanStack Query v5 | Nhất quán với Web |
| Client state | Zustand v5 | Nhất quán với Web |
| HTTP | Axios | Shared config pattern với Web |
| Auth token | expo-secure-store | Lưu token an toàn (không dùng AsyncStorage cho token) |
| Notifications | expo-notifications | Push notification khi có cảnh báo |
| Charts | Victory Native | Battery health chart, SOH trend |

## Packages cần cài

```bash
npx expo install expo-router expo-secure-store expo-notifications
npm install @tanstack/react-query zustand axios
```

---

## Cấu trúc thư mục — File-based routing (Expo Router)

```
app/
├── _layout.tsx                  ← Root layout: QueryClient, AuthProvider, ThemeProvider
├── index.tsx                    ← Redirect theo role sau login
├── (auth)/
│   ├── _layout.tsx              ← AuthLayout (centered card)
│   ├── login.tsx                ← Login screen
│   └── forgot-password.tsx
│
├── (customer)/                  ← Tab group cho Customer
│   ├── _layout.tsx              ← Tab navigator
│   ├── dashboard.tsx            ← Tổng quan pin
│   ├── batteries/
│   │   ├── index.tsx            ← Danh sách pin
│   │   └── [id].tsx             ← Chi tiết pin + SOH chart
│   ├── tickets/
│   │   ├── index.tsx            ← Danh sách ticket
│   │   ├── [id].tsx             ← Chi tiết ticket
│   │   └── create.tsx           ← Tạo ticket mới
│   └── notifications.tsx        ← Cảnh báo + alerts
│
└── +not-found.tsx               ← 404 screen

src/
├── components/
│   ├── ui/                      ← Base components (Button, Card, Badge...)
│   ├── layout/
│   │   └── TabBar.tsx           ← Custom tab bar
│   └── common/                  ← LoadingSpinner, ErrorBoundary, EmptyState
├── features/
│   ├── auth/
│   │   ├── hooks/               ← useLogin, useLogout
│   │   ├── services/            ← auth.service.ts
│   │   └── types/
│   ├── batteries/
│   │   ├── components/          ← BatteryCard, SOHChart, StatusBadge
│   │   ├── hooks/               ← useBatteries, useBatteryDetail
│   │   ├── services/            ← battery.service.ts
│   │   └── types/
│   └── tickets/
│       ├── components/          ← TicketCard, CreateTicketForm
│       ├── hooks/               ← useTickets, useCreateTicket
│       ├── services/            ← ticket.service.ts
│       └── types/
├── lib/
│   ├── axios.ts                 ← Axios instance + interceptors
│   └── secureStore.ts           ← Wrapper expo-secure-store (getToken, setToken, clearToken)
└── stores/
    └── sessionStore.ts          ← Zustand: token, user (nhất quán với Web)
```

---

## Naming Conventions

| Type | Pattern | Ví dụ |
|------|---------|-------|
| Screen (app/) | `{name}.tsx` (lowercase) | `dashboard.tsx` |
| Dynamic route | `[id].tsx` | `[id].tsx` |
| Component | `{Name}.tsx` (PascalCase) | `BatteryCard.tsx` |
| Hook | `use{Name}.ts` | `useBatteries.ts` |
| Service | `{name}.service.ts` | `battery.service.ts` |

---

## Nguyên tắc

- Không eject khỏi Expo managed workflow trong scope capstone
- Không dùng `AsyncStorage` để lưu token — dùng `expo-secure-store`
- Axios config (base URL, interceptors) giữ nhất quán với Web (`src/lib/axios.ts`)
- Zustand store structure nhất quán với Web (`sessionStore.ts`)
- Không thêm package mới nếu stack hiện tại đủ giải quyết — hỏi Leader trước
- Không gọi API trong component — luôn qua `services/` → TanStack Query hook
