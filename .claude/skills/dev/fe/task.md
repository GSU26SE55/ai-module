# Skill: /kltn-task (FE)

## Kích hoạt
`/kltn-task KAN-XX` — làm việc trên Jira ticket phía Frontend (Web hoặc Mobile).

---

## Quy trình

### Bước 1 — Đọc ticket
Fetch từ Jira, xác định:
- **Web** (ReactJS) hay **Mobile** (React Native / Expo)?
- Output mong đợi là gì? (màn hình, component, API call nào?)
- Có dependency với ticket BE nào không?

### Bước 2 — Lập Implementation Plan & viết plan.md

Phân tích ticket và viết file plan tại `logs/KAN-XX/plan.md` với nội dung:

```markdown
# Plan — KAN-XX: [Tên ticket]

## Mục tiêu
[Ticket yêu cầu làm gì, output là gì]

## Các file sẽ tạo/sửa
| File | Hành động | Mô tả |
|------|-----------|-------|
| path/to/file.tsx | create/modify | ... |

## Approach
[Cấu trúc component, state management, API calls]

## Dependencies & Edge Cases
- Loading state, error state, empty state, auth redirect
- Dependency với ticket BE nào không?

## Ước tính
- Size: Small / Medium / Large
- Thời gian: X giờ
```

> **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi làm bất cứ bước nào tiếp theo.**
> Ticket Large phải hỏi Leader sau khi được approve.
> **TUYỆT ĐỐI KHÔNG CODE khi chưa có xác nhận. Không có ngoại lệ, dù ticket nhỏ đến đâu.**

### Bước 3 — Tạo branch
```bash
git checkout -b feature/KAN-XX-ten-tinh-nang
```

### Bước 4 — Implement theo đúng cấu trúc

**Web (ReactJS) — Feature-based + Shared:**
```
features/<tên-feature>/
  pages/        ← route entry: layout + gọi hook, không có logic
  components/   ← UI components của feature này
  hooks/        ← TanStack Query (useQuery / useMutation)
  services/     ← Axios API calls qua axiosInstance (KHÔNG fetch trong component)
  schemas/      ← Zod schema cho form validation
  types/        ← TypeScript types của feature

shared/
  components/layout/   ← AppLayout, AuthLayout, Sidebar, Header
  components/common/   ← LoadingSpinner, ErrorBoundary, EmptyState
  components/ui/       ← shadcn components
  lib/axios.ts         ← Axios instance (không tạo instance mới)
  stores/sessionStore  ← Zustand auth state (không tạo store mới cho auth)
  types/api.types.ts   ← ResponseData<T>, PaginationResponse<T>
```

**Không đặt file mới vào `shared/` trừ khi dùng ở ≥ 2 feature khác nhau.**

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
- Không hardcode URL / token
- Route cần auth đã có protected wrapper
- Responsive đúng (Web)

### Bước 6 — Commit
```bash
git add <files cụ thể>
git commit -m "feat(KAN-XX): mô tả ngắn"
```

### Bước 7 — Cập nhật Jira
Chuyển ticket sang **IN PROGRESS**.

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
