# Skill: /kltn-reviewpr (BE)

## Kích hoạt
`/kltn-reviewpr KAN-XX` — review PR của đồng đội phía Backend trước khi approve merge.

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
   - [ ] Checklist test đã được tích?

3. **Chạy checklist code** (góc nhìn outsider — không phải tác giả)

---

## Checklist

### Architecture
- [ ] Controller chỉ validate + delegate, không chứa business logic?
- [ ] Service không gọi thẳng DbContext?
- [ ] Repository chỉ làm việc với DB?

### Code Quality
- [ ] FluentValidation đặt đúng chỗ (request DTO)?
- [ ] EF Core query không có N+1 tiềm ẩn?
- [ ] Không có giá trị hardcode (connection string, secret, URL)?
- [ ] Tên method/class đúng PascalCase?

### Security
- [ ] Endpoint cần auth đã có `[Authorize]`?
- [ ] Role check đúng (Admin / Manager / Staff)?
- [ ] Response không leak thông tin nhạy cảm?

### TimescaleDB / Redis
- [ ] Time-series data dùng TimescaleDB đúng, không dùng PostgreSQL thường?
- [ ] Cache Redis có TTL hợp lý?

### Migration
- [ ] Có migration mới không? Nếu có — migration có thể rollback an toàn?
- [ ] Không có breaking change với dữ liệu hiện tại?

### Conflict
- [ ] Branch không có conflict với `main`?
- [ ] Không override code của người khác đang làm?

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
