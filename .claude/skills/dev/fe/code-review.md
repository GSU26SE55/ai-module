# Skill: /kltn-reviewcode (FE)

## Kích hoạt
`/kltn-reviewcode` — review code FE trước khi ship.

---

## Checklist

### Architecture
- [ ] Không có business logic trong component (chỉ UI + state)?
- [ ] API call qua `services/` layer, không fetch trực tiếp?
- [ ] Global state dùng Zustand, không prop-drill quá 2 cấp?

### Code Quality
- [ ] Component đặt tên PascalCase?
- [ ] Không hardcode URL, token, config (dùng `.env`)?
- [ ] Loading và error state được xử lý?
- [ ] Không có `console.log` còn sót lại?

### UI / UX
- [ ] Dùng đúng shadcn/ui components (Web), không tự custom lại những gì đã có?
- [ ] Responsive trên mobile viewport (Web)?
- [ ] Expo Router navigation đúng pattern (Mobile)?

### Auth & Security
- [ ] Route cần auth có protected wrapper?
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
logs/KAN-XX-ten-feature/review.md
```
Copy từ `logs/_template/review.md`, điền kết quả thực tế.
Nếu folder chưa tồn tại → tạo mới.
