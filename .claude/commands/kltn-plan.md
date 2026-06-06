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
- **Nếu tồn tại** → Hiện nội dung plan đã có. Kiểm tra `Status`:

  | Status | Hành động |
  |--------|-----------|
  | `PLANNING` | Hỏi: **[1] Dùng plan này** → chạy `/kltn-implement $ARGUMENTS` / **[2] Cập nhật plan** → tiếp tục Bước 1 |
  | `IN_PROGRESS` | Nhắc "Plan đang được implement. Chạy `/kltn-implement $ARGUMENTS` để tiếp tục." Dừng. |
  | `REVIEWING` | Nhắc "Đang chờ review. Chạy `/kltn-reviewcode $ARGUMENTS`." Dừng. |
  | `TESTING` | Nhắc "Đang ở giai đoạn test. Chạy `/kltn-test $ARGUMENTS`." Dừng. |
  | `SHIPPED` | Nhắc "Đang chờ PR merge." Dừng. |
  | `MERGED` | Nhắc "Task đã hoàn thành." Dừng. |

- **Nếu chưa tồn tại** → Tiếp tục Bước 1.

---

**Bước 1 — Đọc GitHub Issue**

```bash
# Đọc issue chính
gh issue view $ARGUMENTS --json number,title,body,labels,milestone,assignees

# Đọc sub-issues (nếu có)
gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/issues/$ARGUMENTS/sub_issues \
  --jq '.[] | {number: .number, title: .title, body: .body, state: .state}'
```

Đọc kỹ:
- **Issue chính:** title, body (Mô tả + Scope + Endpoints + Approach + Steps + Edge Cases + Acceptance Criteria), labels, milestone, assignees.
- **Sub-issues (nếu có):** title, body, state của từng sub-issue — plan chi tiết hoặc scope có thể đã được cập nhật tại đây. Tổng hợp thông tin từ tất cả sub-issues vào phân tích ở Bước 2.

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
**Trong scope:**
- ...

**Ngoài scope:**
- ...

## Endpoints
| Method | Path | Mục đích / Request / Response |
|--------|------|-------------------------------|
| GET | `/api/...` | ... |

(Bỏ section này nếu task không có endpoint)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| path/to/file | create/modify | ... |

## Approach
[Data flow / API design — tối đa 5 bullet, dựa trên answers từ Bước 3]

## Edge Cases
- Input không hợp lệ: ...
- Error handling: ...

## Acceptance Criteria
- [ ] [Tiêu chí cụ thể, verify được]
- [ ] ...

## Steps
[Dùng bảng template bên dưới theo role — mỗi dòng là 1 checkbox]
- [ ] Bước 1: ...
- [ ] Bước 2: ...

## Câu hỏi đã giải đáp
[Tóm tắt những điểm đã hỏi và câu trả lời — để reviewer hiểu context]
```

> **Step template theo role** — chọn cột theo role, mỗi dòng là 1 checkbox trong Steps:
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

- User chọn **1 / approve / ok / yes / y / tiến hành** → thực hiện Bước 7.
- User chọn **2 / chỉnh sửa** → cập nhật plan theo góp ý → hiện lại. Lặp cho đến khi approve.

---

**Bước 7 — Finalize: post lên issue + cập nhật label**

```bash
# Update body của issue với plan chi tiết (thay thế placeholder)
# Lưu ý: dùng <<EOF (không có single-quote) để biến được expand
gh issue edit $ARGUMENTS --body "$(cat <<EOF
## 📋 Plan — GH-$ARGUMENTS

**Dev:** [tên từ CLAUDE.local.md]
**Ngày lập plan:** $(date +%Y-%m-%d)

## Mô tả
[copy Mục tiêu từ plan.md]

## Scope
**Trong scope:**
[copy từ plan.md]

**Ngoài scope:**
[copy từ plan.md]

## Endpoints
[copy từ plan.md — bỏ section này nếu không có endpoint]

## Approach
[copy từ plan.md]

## Steps
[copy danh sách steps từ plan.md]

## Edge Cases
[copy từ plan.md]

## Acceptance Criteria
[copy Success Criteria từ plan.md dưới dạng checklist]

---
> Plan đầy đủ (files, câu hỏi đã giải đáp): \`logs/GH-$ARGUMENTS/plan.md\`
EOF
)"

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

---

**⚠️ Khi có thay đổi đột xuất trong lúc implement**

Nếu scope, approach, hoặc files thay đổi so với plan đã approve (do phát hiện blocker, yêu cầu mới, hoặc technical constraint):

1. **Cập nhật `logs/GH-$ARGUMENTS/plan.md`** — ghi rõ thay đổi gì, lý do tại sao.
2. **Sync lại body của issue ngay sau khi xác nhận thay đổi:**

```bash
# Lưu ý: dùng <<EOF (không có single-quote) để biến được expand
gh issue edit $ARGUMENTS --body "$(cat <<EOF
[nội dung plan mới — copy từ plan.md đã cập nhật]
EOF
)"
```

> **Nguyên tắc:** Issue body phải luôn phản ánh trạng thái plan **hiện tại** — không để body và plan.md bị lệch nhau. Reviewer và team đọc issue body, không đọc file local.

Không cần approve lại nếu thay đổi nhỏ (thêm/bớt file, điều chỉnh approach). Nếu thay đổi lớn (scope mới, approach hoàn toàn khác) → dừng implement, hỏi user trước.
