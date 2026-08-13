# Skill: /kltn-debug (BE)

## Kích hoạt
`/kltn-debug [issue-number]` — fix bug từ issue được tạo bởi log sheet.

---

## ACTION-FIRST RULE

**Đọc issue body thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels
```

Tool calls trước, text output sau. Không đoán lỗi từ title.

---

## Phân tích lỗi BE

### 1. Đọc stack trace / mô tả lỗi

Từ body issue, xác định:
- **Exception type:** `NullReferenceException`, `DbUpdateException`, `UnauthorizedAccessException`...
- **File:line** nếu có trong stack trace
- **Endpoint** bị lỗi (`POST /api/batteries`, `GET /api/tickets/{id}`...)
- **Input** gây ra lỗi (request body, query params)

### 2. Trace nguyên nhân theo layer

```
Controller → Handler → Repository → Entity
```

Đọc code tại file:line từ stack trace. Nếu không có stack trace → đọc Handler liên quan đến endpoint.

### 3. Common root causes BE

| Triệu chứng | Nguyên nhân thường gặp |
|------------|----------------------|
| `NullReferenceException` tại Handler | Entity null sau `GetByIdAsync` — thiếu null check |
| `await UpdateAsync` / `await DeleteAsync` | Await void method — remove `await` |
| `await GetAllAsync()` build lỗi hoặc runtime | GetAllAsync là SYNC — remove `await` |
| Query trả về deleted record | Thiếu `.Where(x => !x.IsDeleted)` |
| 401 Unauthorized | Thiếu `[Authorize]` trên endpoint |
| 403 Forbidden | Role claim sai hoặc policy chưa config |
| Migration fail | NOT NULL column thiếu `defaultValue` hoặc chưa seed |
| Duplicate key | Thiếu `AnyAsync` check trước khi `AddAsync` |
| Transaction rollback ẩn | Exception bị swallow — thêm logging trong catch |

### 4. Verify trước khi fix

```bash
# Build để chắc không có syntax error
dotnet build --no-restore -v quiet

# Chạy test liên quan
dotnet test --no-build --filter "ClassName=BatteryCommandHandlerTests" -v minimal
```

---

## Checklist fix

- [ ] Fix đúng hypothesis — không sửa code không liên quan
- [ ] Null check đủ: `entity == null` → return `IsSuccess = false`
- [ ] `IsDeleted` check: `entity.IsDeleted` → return `IsSuccess = false`
- [ ] `GetAllAsync()` không có `await`
- [ ] `UpdateAsync()` / `DeleteAsync()` không có `await`
- [ ] Query có `.Where(x => !x.IsDeleted)`
- [ ] `dotnet build` — không lỗi sau khi fix

---

## Commit message

```
fix(#$ISSUE_NUMBER): [mô tả ngắn — ví dụ: null check GetById Battery handler]
```
