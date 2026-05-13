# Skill: /kltn-reviewcode (BE)

## Kích hoạt
`/kltn-reviewcode` — review code BE trước khi ship.

---

## ACTION-FIRST RULE

**Đọc diff thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
git diff main...HEAD
# hoặc nếu đã stage: git diff --staged
```

Không nhận xét từ memory hay đọc code lướt qua. Tool calls trước, text output sau.

---

## Effort Scaling

| Level | Khi nào | Làm gì |
|-------|---------|--------|
| **Quick** | 1 file nhỏ, thay đổi ít | Chỉ check Critical items + 2–3 Warning |
| **Standard** | 1 ticket / 1 feature | Full checklist, phân tích từng vấn đề |
| **Deep** | PR nhiều file, cross-service | Full checklist + cross-file consistency + DI chain |
| **Exhaustive** | Cuối sprint / refactor lớn | Full + architecture review + regression risk |

---

## Xác định issue number

```bash
git branch --show-current | grep -oE 'GH-[0-9]+'
# feature/GH-12-battery-crud → TICKET_ID = GH-12
```

Nếu không xác định được → hỏi user trước khi tiếp tục.

---

## Checklist

### Architecture (CQRS + Clean Architecture)
- [ ] Controller chỉ gọi `_mediator.Send()` — không chứa logic?
- [ ] CommandHandler chỉ inject `IUnitOfWork` — không inject `DbContext` trực tiếp?
- [ ] QueryHandler không gọi `SaveChangesAsync()`?
- [ ] Không có Service layer — logic đặt trong Handler, không tạo class `XxxService`?

### Code Quality
- [ ] Validation dùng `ValidateAsync()` (IValidatable<T>), không dùng FluentValidation?
- [ ] `GetAllAsync()` không có `await` (SYNC — trả IQueryable)?
- [ ] `UpdateAsync()` / `DeleteAsync()` không có `await` (void methods)?
- [ ] Query luôn có `.Where(x => !x.IsDeleted)` (không có global query filter)?
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

## Adversarial Self-Review

Trước khi nộp báo cáo:

1. **Đã đọc diff chưa?** — Không được nhận xét từ memory, phải đọc code thực tế
2. **Mỗi Critical có evidence (file:line) không?** — Không claim lỗi chung chung
3. **Cách fix có cụ thể không?** — "Xóa `await`" tốt hơn "sửa lại"
4. **Có bỏ sót security check không?** — Auth, role, data leak là ưu tiên cao nhất
5. **Kết luận PASS/FAIL có nhất quán với danh sách lỗi không?** — Có Critical → phải FAIL

---

## Định dạng báo cáo

Sau khi review xong, **bắt buộc ghi file** (dùng Write tool):

```
logs/GH-[number]/review.md
```
(TICKET_ID đã xác định ở trên, ví dụ: `logs/GH-12/review.md`)

Nếu folder chưa tồn tại → tạo mới. Nội dung file:

```markdown
## BÁO CÁO CODE REVIEW — [branch] — [YYYY-MM-DD]
### Scope: BE
### Effort: [Quick / Standard / Deep / Exhaustive]

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

---

## Common Anti-Patterns

### Claim PASS mà không đọc diff

**SAI:**
```
Đọc tên file → "Trông có vẻ đúng cấu trúc" → KẾT LUẬN: ✅ PASS
```
_Vấn đề:_ Không phát hiện `await GetAllAsync()` hay `await UpdateAsync()` — lỗi runtime khi chạy.

**ĐÚNG** — Đọc diff trước, ghi evidence cụ thể:
```
git diff main...HEAD | grep -n "await.*GetAllAsync\|await.*UpdateAsync\|await.*DeleteAsync"
# → BatteryCommandHandler.cs:34: await _unitOfWork.Batteries.UpdateAsync(entity);
# 🔴 Critical: BatteryCommandHandler.cs:34 — UpdateAsync là void method, remove `await`
```

---

### Chỉ check happy path, bỏ qua auth và soft delete

**SAI:**
```
✅ Pass: logic tạo entity đúng
KẾT LUẬN: PASS
```

**ĐÚNG** — Kiểm tra đủ:
```
✅ Pass: logic tạo entity đúng
🔴 Critical: BatteryController.cs:45 — [HttpDelete] thiếu [Authorize(Policy="AdminOnly")]
🔴 Critical: BatteryGetListQueryHandler.cs:12 — thiếu .Where(x => !x.IsDeleted)
KẾT LUẬN: FAIL — 2 Critical chưa fix
```
