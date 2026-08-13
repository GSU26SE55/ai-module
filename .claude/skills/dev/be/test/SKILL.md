# Skill: /kltn-test (BE)

## Kích hoạt
`/kltn-test GH-[number]` — chạy test BE sau khi `/kltn-reviewcode` PASS.

---

## ACTION-FIRST RULE

**Chạy lệnh test thực sự TRƯỚC khi viết báo cáo.** Không đoán kết quả từ việc đọc code. Không bao giờ claim "PASS" khi chưa chạy lệnh. Tool calls trước, text output sau.

---

## Effort Scaling

| Level | Khi nào | Làm gì |
|-------|---------|--------|
| **Quick** | 1 endpoint / 1 handler đơn giản | Happy path + 1–2 edge case |
| **Standard** | 1 ticket / 1 feature hoàn chỉnh | Happy path + edge cases + auth + validation |
| **Deep** | PR chuẩn bị merge | Unit test + integration test + role-based access + error handling |
| **Exhaustive** | Cuối sprint / trước demo | Toàn bộ endpoints, tất cả role, SLA timer, regression test |

---

## Bước 1 — Xác định ticket

Issue number lấy từ argument của lệnh. Nếu không có:
```bash
git branch --show-current | grep -oE 'GH-[0-9]+'
# feat/GH-12-battery-crud → GH-12
```

---

## Bước 2 — Chuẩn bị môi trường

- Không test production — chỉ test local
- Seed database test nếu cần
- Đảm bảo `dotnet build` thành công trước khi test

---

## Bước 3 — Chạy unit tests

```bash
dotnet test --no-build --verbosity minimal
```

Ghi lại: số test pass / fail / skip.

---

## Bước 4 — Chạy với coverage

```bash
dotnet test --collect:"XPlat Code Coverage" --verbosity minimal
```

Target: **≥ 80% line coverage**. CI fail nếu < 80%.

---

## Bước 5 — Checklist test bắt buộc

Với mỗi ticket BE:

- [ ] Unit test cho `CommandHandler` — mock `IUnitOfWork`, test business logic
- [ ] Unit test cho `QueryHandler` — mock `IUnitOfWork`, test query + filter
- [ ] Integration test cho endpoint — happy path (input hợp lệ, response đúng format)
- [ ] Edge case — input rỗng, null, sai kiểu → 400 với message rõ ràng
- [ ] Auth — `[Authorize]` endpoint phải 401 khi không có token
- [ ] Role — Admin/Manager/Staff không truy cập endpoint của nhau (403)
- [ ] Soft delete — query phải filter `IsDeleted = false`

Nếu thiếu test case → báo FAIL, yêu cầu dev bổ sung trước khi ship.

---

## Adversarial Self-Review

Trước khi nộp báo cáo:

1. **Test case có thực sự chạy không?** — Không được claim PASS nếu không có output lệnh
2. **Bug có steps to reproduce rõ ràng không?** — Dev khác phải reproduce được mà không hỏi thêm
3. **Đã test edge cases chưa?** — Input rỗng, null, sai kiểu, concurrent
4. **Auth và role đã test chưa?** — Không có token → 401, sai role → 403
5. **Soft delete filter đã check chưa?** — Thiếu `.Where(x => !x.IsDeleted)` → data bẩn

---

## Định dạng báo cáo

Sau khi chạy test xong, **bắt buộc ghi file** (dùng Write tool):

```
logs/GH-[number]/test.md
```

Nếu folder chưa tồn tại → tạo mới. Nội dung file:

```markdown
## TEST REPORT — GH-[number] — [YYYY-MM-DD]
### Scope: BE
### Môi trường: local

### TÓM TẮT
[1–2 câu về kết quả tổng thể]

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| GET /api/batteries — happy path | Bearer token hợp lệ | 200 + list | ... | ✅ PASS |
| GET /api/batteries — no token | không có Bearer | 401 | ... | ✅ PASS |
| POST /api/batteries — missing name | body rỗng | 400 | ... | ❌ FAIL |

### Coverage
- Line coverage: X% (target ≥ 80%)

### Bugs tìm được
- 🔴 [Critical] POST /api/batteries không validate name rỗng → 500 thay vì 400
  - Steps: `curl -X POST http://localhost:5000/api/batteries -d '{}'`
  - Expected: 400 "Name is required"
  - Actual: 500 Internal Server Error

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

---

## Common Anti-Patterns

### Claim PASS mà không chạy test thực sự

**SAI:**
```
Đọc code handler → "Logic có vẻ đúng" → Báo cáo: ✅ PASS
```
_Vấn đề:_ Code đọc đúng không nghĩa runtime đúng. Có thể lỗi DI, migration, config.

**ĐÚNG** — Chạy lệnh thực sự, ghi output:
```bash
dotnet test --no-build --verbosity minimal
# Output: Test Run Successful. Total: 12, Passed: 12, Failed: 0
# → ✅ PASS với evidence
```

---

### Chỉ test happy path, bỏ qua auth và edge case

**SAI:**
```
| POST /batteries valid data | 201 OK | 201 OK | ✅ PASS |
KẾT LUẬN: PASS
```

**ĐÚNG** — Test đầy đủ:
```
| POST /batteries valid data    | 201 + id    | 201 + id    | ✅ PASS |
| POST /batteries missing name  | 400         | 500 (!)     | ❌ FAIL |
| POST /batteries no token      | 401         | 401         | ✅ PASS |
| POST /batteries Staff role    | 403         | 200 (!)     | ❌ FAIL |
```
