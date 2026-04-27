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

**Web (ReactJS):**
```
pages/          ← route entry, chỉ layout + data fetching
components/     ← UI components (stateless ưu tiên)
stores/         ← Zustand global state
services/       ← Axios API calls (KHÔNG fetch trong component)
```

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
**Web:** ReactJS 18 · Zustand · Axios · shadcn/ui · Tailwind · Recharts
**Mobile:** React Native · Expo · Expo Router · Axios
