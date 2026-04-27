# Skill: /kltn-reviewcode (BE)

## Kích hoạt
`/kltn-reviewcode` — review code BE trước khi ship.

---

## Checklist

### Architecture
- [ ] Controller chỉ validate + delegate, không chứa logic?
- [ ] Service không gọi thẳng DbContext?
- [ ] Repository chỉ làm việc với DB, không có logic?

### Code Quality
- [ ] FluentValidation đặt ở đúng chỗ (request DTO)?
- [ ] EF Core query tránh N+1 (dùng `.Include()` khi cần)?
- [ ] Không hardcode bất kỳ giá trị nào (dùng `appsettings.json`)?
- [ ] Tên method/class đúng PascalCase (C# convention)?

### Security
- [ ] Endpoint cần auth đã có `[Authorize]`?
- [ ] Role check đúng (Admin / Manager / Staff)?
- [ ] Response không leak thông tin nhạy cảm?

### TimescaleDB / Redis
- [ ] Time-series data dùng TimescaleDB, không PostgreSQL thường?
- [ ] Cache Redis có TTL hợp lý?

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

