# Skill: /kltn-reviewpr (FE)

## Kích hoạt
`/kltn-reviewpr KAN-XX` — review PR của đồng đội phía Frontend (Web hoặc Mobile) trước khi approve merge.

---

## Quy trình

1. **Đọc PR** — lấy diff và PR description
   ```bash
   gh pr view <số PR hoặc KAN-XX> --json title,body,files
   gh pr diff <số PR hoặc KAN-XX>
   ```

2. **Kiểm tra PR description** trước khi đọc code:
   - [ ] Có ticket ID (KAN-XX)?
   - [ ] Mô tả thay đổi rõ ràng?
   - [ ] Checklist test đã được tích (browser/device)?

3. **Chạy checklist code** (góc nhìn outsider — không phải tác giả)

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
- [ ] Không hardcode URL, token, config (phải dùng `.env`)?
- [ ] Loading và error state được xử lý?
- [ ] Không còn `console.log` sót lại?

### UI / UX
- [ ] UI primitive dùng từ `shared/components/ui` (shadcn generated components)?
- [ ] Không tự custom Button/Input/Form/Dialog/Table/Badge/Skeleton nếu shadcn đã có?
- [ ] Primitive mới được thêm bằng `npx shadcn@latest add <component>`?
- [ ] Responsive trên mobile viewport (Web)?
- [ ] Expo Router navigation đúng pattern (Mobile)?

### Auth & Security
- [ ] Route cần auth có protected wrapper?
- [ ] Token không lưu trong `localStorage` plain text?
- [ ] Không render sensitive data ra UI không cần thiết?

### Conflict
- [ ] Branch không có conflict với `main`?
- [ ] Không override component/store người khác đang sửa?

---

## Output
```
## BÁO CÁO PR REVIEW — KAN-XX — [YYYY-MM-DD]
### Reviewer: [tên bạn]
### TÓM TẮT
[1–2 câu về PR]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### KHUYẾN NGHỊ
- Ngay lập tức: ...

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[APPROVE / REQUEST CHANGES] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Nếu REQUEST CHANGES → comment rõ trên PR, không approve.
