# Skill: /kltn-reviewcode (FE)

## Kích hoạt
`/kltn-reviewcode` — review code FE trước khi ship.

---

## Checklist

### Architecture
- [ ] Không có business logic trong component (chỉ UI + state)?
- [ ] API call qua `services/` layer → hook TanStack Query, không fetch trực tiếp trong component?
- [ ] File mới đặt đúng chỗ: `features/<tên>/` cho code của feature, `shared/` chỉ khi dùng ≥ 2 feature?
- [ ] `features/<A>` không import trực tiếp từ `features/<B>`?
- [ ] Zustand (`sessionStore`) chỉ cho auth session — không dùng cho server state?
- [ ] Không tạo Axios instance mới — dùng `shared/lib/axios.ts`?

### Code Quality
- [ ] Component đặt tên PascalCase?
- [ ] Không hardcode URL, token, config (dùng `.env`)?
- [ ] Loading và error state được xử lý?
- [ ] Không có `console.log` còn sót lại?

### UI / UX
- [ ] UI primitive dùng từ `shared/components/ui` (shadcn generated components)?
- [ ] Không tự custom Button/Input/Form/Dialog/Table/Badge/Skeleton nếu shadcn đã có?
- [ ] Primitive mới được thêm bằng `npx shadcn@latest add <component>`?
- [ ] Responsive trên mobile viewport (Web)?
- [ ] Expo Router navigation đúng pattern (Mobile)?

### Auth & Security
- [ ] Route mới đã khai báo trong `router/index.tsx`?
- [ ] Page cần auth đã wrap `ProtectedRoute`?
- [ ] Page có role restriction đã wrap `RoleRoute` (Admin / Manager / Staff)?
- [ ] Token không lưu trong `localStorage` plain text?
- [ ] Không render sensitive data ra UI không cần thiết?

---

## Output
```
## BÁO CÁO CODE REVIEW — [branch]
### TÓM TẮT
[1–2 câu về trạng thái tổng thể]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Sau khi có kết quả, lưu vào:
```
logs/KAN-XX/review.md
```
Nếu folder chưa tồn tại → tạo mới.