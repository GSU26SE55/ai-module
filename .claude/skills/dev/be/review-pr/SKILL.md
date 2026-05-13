# Skill: /kltn-reviewpr (BE)

## Kích hoạt
`/kltn-reviewpr GH-XX / #[number]` — review PR của đồng đội phía Backend trước khi approve merge.

---

## Quy trình

1. **Đọc PR** — lấy diff và PR description
   ```bash
   gh pr view <số PR hoặc GH-XX / #[number]> --json title,body,files
   gh pr diff <số PR hoặc GH-XX / #[number]>
   ```

2. **Kiểm tra PR description** trước khi đọc code:
   - [ ] Có ticket ID (GH-XX / #[number])?
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
- [ ] Validation dùng `IValidatable<T>` + `ValidateAsync()` — KHÔNG dùng FluentValidation?
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
## BÁO CÁO PR REVIEW — GH-XX / #[number] — [YYYY-MM-DD]
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

Nếu **REQUEST CHANGES**:
```bash
gh pr review $PR_NUMBER --request-changes --body "[mô tả vấn đề cần sửa]"

# Chuyển ticket về In Progress để author biết cần sửa
gh issue edit $ISSUE_NUMBER \
  --remove-label "status: reviewing" \
  --add-label "status: implementing"
```
> Ticket tự động chuyển từ **In Review → In Progress** trên Sprint Board.

Nếu **APPROVE**:
```bash
gh pr review $PR_NUMBER --approve --body "LGTM ✅ — [1 câu tóm tắt]"
```
> Ticket giữ nguyên ở cột **In Review**. Author chạy `/kltn-complete $ISSUE_NUMBER` để merge và chuyển sang **Completed**.
