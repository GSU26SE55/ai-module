Lập kế hoạch cho GitHub Issue. Chạy TRƯỚC khi `/kltn-implement`.

Issue number: `$ARGUMENTS`

---

## ⚠️ NGUYÊN TẮC BẮT BUỘC

> **Không bao giờ đoán mò. Nếu bất kỳ điểm nào chưa rõ về task hoặc workflow → DỪNG và hỏi ngay.**
>
> Thà hỏi 5 câu trước khi bắt đầu, còn hơn code sai hướng rồi phải làm lại.
>
> Plan chỉ được tạo khi tất cả câu hỏi đã được trả lời.

---

**Bước 0 — Kiểm tra plan hiện tại**

Đọc `logs/GH-$ARGUMENTS/plan.md`:
- **Nếu tồn tại** → Hiện nội dung plan đã có. Hỏi:
  ```
  Plan đã tồn tại (Status: [status]).
  [1] Dùng plan này → chạy /kltn-implement $ARGUMENTS để bắt đầu code
  [2] Cập nhật plan — thay đổi approach hoặc scope
  ```
  Nếu chọn 1 → Dừng. Nếu chọn 2 → tiếp tục Bước 1.
- **Nếu chưa tồn tại** → Tiếp tục Bước 1.

---

**Bước 1 — Đọc GitHub Issue**

```bash
gh issue view $ARGUMENTS --json number,title,body,labels,milestone,assignees
```

Đọc kỹ: title, body (Mục tiêu + Acceptance Criteria + Ghi chú kỹ thuật), labels, milestone, assignees.

---

**Bước 2 — Phân tích gap (QUAN TRỌNG)**

Sau khi đọc issue, phân tích các mục sau. Với mỗi mục, đánh dấu **✅ Rõ** hoặc **❓ Chưa rõ**:

| Mục | Câu hỏi kiểm tra | Trạng thái |
|-----|-----------------|-----------|
| **Mục tiêu** | Task cần làm gì? Output cuối là gì? | ✅ / ❓ |
| **Scope** | Có gì nằm trong scope, gì ngoài scope? | ✅ / ❓ |
| **Acceptance criteria** | Mỗi tiêu chí có đủ cụ thể để viết test không? | ✅ / ❓ |
| **Technical approach** | Biết implement thế nào chưa? (endpoint, data flow, component…) | ✅ / ❓ |
| **Dependencies** | Issue này phụ thuộc issue/PR nào? Service nào đã có sẵn? | ✅ / ❓ |
| **Edge cases** | Input không hợp lệ xử lý thế nào? Error cases ra sao? | ✅ / ❓ |
| **Workflow fit** | Task này ở phase nào trong sprint? Ai review? | ✅ / ❓ |

---

**Bước 3 — Hỏi khi chưa rõ**

Nếu có bất kỳ mục nào đánh dấu **❓ Chưa rõ** → **DỪNG và hỏi ngay**, không viết plan trước.

Liệt kê **tất cả câu hỏi trong 1 lần**, gộp theo chủ đề, ưu tiên câu ảnh hưởng đến approach nhất:

```
Trước khi lập plan cho GH-$ARGUMENTS, tôi cần làm rõ một số điểm:

**Về scope:**
1. [Câu hỏi cụ thể] — vì [lý do cần biết]
2. ...

**Về technical approach:**
3. [Câu hỏi cụ thể] — vì [lý do cần biết]

**Về acceptance criteria:**
4. [Câu hỏi cụ thể] — vì [lý do cần biết]

Trả lời xong tôi sẽ viết plan ngay.
```

> Không đặt câu hỏi chung chung như "Bạn muốn tôi làm gì?".
> Mỗi câu hỏi phải kèm lý do tại sao cần biết (ảnh hưởng đến approach / test / architecture).

Chờ user trả lời. Nếu câu trả lời vẫn còn điểm chưa rõ → hỏi tiếp (tối đa 2 vòng).
Sau khi tất cả ❓ đã được giải đáp → tiếp tục Bước 4.

---

**Bước 4 — Đọc rules theo role**

Đọc `CLAUDE.local.md` → xác định role → đọc rules tương ứng:
- BE → `rules/tech/be.md`
- FE → `rules/tech/fe.md`
- AI → `rules/tech/ai.md`

---

**Bước 5 — Viết plan.md**

Tạo `logs/GH-$ARGUMENTS/plan.md`:

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING | **Role:** BE/FE/AI | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [GitHub URL]
- **Sprint:** [milestone]

## Mục tiêu
[1–3 dòng: issue yêu cầu gì, output mong đợi — dựa trên đã hiểu rõ ở Bước 2–3]

## Scope
- Trong scope: ...
- Ngoài scope: ...

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| path/to/file | create/modify | ... |

## Approach
[Data flow / API design — tối đa 5 bullet, dựa trên answers từ Bước 3]

## Edge Cases
- Input không hợp lệ: ...
- Error handling: ...

## Steps
- [ ] Bước 1: ...
- [ ] Bước 2: ...

## Câu hỏi đã giải đáp
[Tóm tắt những điểm đã hỏi và câu trả lời — để reviewer hiểu context]
```

> **Step template theo role:**
>
> | BE | FE | AI |
> |----|----|----|
> | Entity + Enum | Types | Preprocess |
> | DTO + Response | Service | Model / training |
> | Command + Handler | Hook(s) | Inference |
> | Query + Handler | Component + Page | FastAPI endpoint |
> | Controller | Unit test | Unit test + latency |
> | Unit test + Migration | | |

---

**Bước 6 — Hiện plan và chờ approve**

Hiện plan.md đã viết và hỏi:

```
Plan cho GH-$ARGUMENTS đã sẵn sàng.

[1] Approve → tôi sẽ post plan lên issue + chuyển label → chạy /kltn-implement $ARGUMENTS để bắt đầu code
[2] Chỉnh sửa → nêu điểm cần thay đổi
```

- User chọn **1 / approve / ok / tiến hành** → thực hiện Bước 7.
- User chọn **2 / chỉnh sửa** → cập nhật plan theo góp ý → hiện lại. Lặp cho đến khi approve.

---

**Bước 7 — Finalize: post lên issue + cập nhật label**

```bash
# Post plan summary lên issue để team theo dõi
gh issue comment $ARGUMENTS --body "## 📋 Plan — GH-$ARGUMENTS

**Dev:** [tên từ CLAUDE.local.md]
**Ngày lập plan:** $(date +%Y-%m-%d)

### Mục tiêu
[copy từ plan.md]

### Approach
[copy từ plan.md]

### Steps
[copy danh sách steps từ plan.md]

> Plan đầy đủ (bao gồm edge cases, files, câu hỏi đã giải đáp): \`logs/GH-$ARGUMENTS/plan.md\`"

# Chuyển label status: init → status: implementing
gh issue edit $ARGUMENTS \
  --remove-label "status: init" \
  --add-label "status: implementing"
```

Cập nhật `plan.md`: `Status: PLANNING → IN_PROGRESS`, `Ngày` → hôm nay.

Sau đó nhắc user:
```
Plan đã được approved và post lên issue.
Chạy /kltn-implement $ARGUMENTS để bắt đầu implement.
```
