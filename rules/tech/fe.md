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
| UI | shadcn/ui + Tailwind v4 | Generate component source vào `src/shared/components/ui`, không cài như UI runtime library |
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

## Nguyên tắc

- Không thêm package mới nếu stack hiện tại đủ giải quyết — hỏi Leader trước
- Không tạo Axios instance mới — dùng `shared/lib/axios.ts`
- Không dùng `localStorage` để lưu token — chỉ dùng cookie qua `js-cookie`
- Không dùng Zustand cho server state — dùng TanStack Query
