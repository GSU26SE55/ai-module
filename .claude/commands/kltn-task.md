Làm việc trên Jira ticket được chỉ định.

**Bước 0 — Kiểm tra plan hiện tại**

Đọc `logs/$ARGUMENTS/plan.md`:

- **Nếu tồn tại** → đọc `Status`:

  | Status | Hành động |
  |--------|-----------|
  | `PLANNING` | Hiện plan + Steps. Hỏi chọn **[1] Execute** hoặc **[2] Chat about**. Nếu Execute → `IN_PROGRESS` + bắt đầu Bước 4. |
  | `IN_PROGRESS` | Tìm `- [ ]` đầu tiên. Tóm tắt "Xong X/Y bước. Tiếp tục Bước Z". Hỏi tiếp tục không. |
  | `REVIEWING` | "Chạy `/kltn-reviewcode` để tiếp tục." Dừng. |
  | `TESTING` | "Chạy `/kltn-test $ARGUMENTS` để tiếp tục." Dừng. |
  | `SHIPPED` | "Đang chờ PR review." Dừng. |
  | `MERGED` | "Ticket đã done." Dừng. |

  **Dừng sau mỗi status — chờ user chỉ dẫn.**

- **Nếu chưa tồn tại** → tiếp tục Bước 1.

---

**Bước 1 — Xác định role**

Đọc `CLAUDE.local.md`. Dùng **Dev Role** nếu có, ngược lại dùng Role:
- BE → `rules/tech/be.md`
- FE → `rules/tech/fe.md`
- AI → `rules/tech/ai.md`

**Bước 2 — Đọc context**

Fetch Jira ticket: `$ARGUMENTS`

**Bước 3 — Viết plan.md**

Tạo `logs/$ARGUMENTS/plan.md`:

```markdown
# Plan — KAN-XX: [Tên ticket]

## Metadata
- **Status:** PLANNING | **Role:** BE/FE/AI | **Ngày:** YYYY-MM-DD

## Mục tiêu
[1–3 dòng: ticket yêu cầu gì, output mong đợi]

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| path/to/file | create/modify | ... |

## Approach
[Data flow / API design — tối đa 5 bullet]

## Steps
- [ ] Bước 1: ...
- [ ] Bước 2: ...
```

**Step template theo role (dùng làm khung, điều chỉnh theo ticket):**

| BE (Clean Architecture) | FE (Feature-based) | AI (FastAPI) |
|-------------------------|--------------------|--------------|
| Entity + Enum | Types (`*.types.ts`) | Preprocess |
| DTO + Response | Service (`*.service.ts`) | Model / training |
| Command + Handler | Hook(s) (`use*.ts`) | Inference |
| Query + Handler | Component + Page | FastAPI endpoint |
| Controller | Unit test | Unit test + latency |
| Unit test (mock UoW) | | |
| Migration | | |

> BE: dùng scaffold khi phù hợp — `/scaffold-entity`, `/scaffold-dto`, `/scaffold-cqrs-command`, `/scaffold-cqrs-query`, `/scaffold-controller`, `/scaffold-crud`, `/run-migration`
> AI: dùng `/scaffold-fastapi-endpoint`

**DỪNG — hiện plan và hỏi user chọn:**

```
Plan đã sẵn sàng. Bạn muốn:
  [1] Execute   — bắt đầu implement ngay
  [2] Chat about — thảo luận / chỉnh sửa plan trước
```

- Nếu user chọn **1 / Execute / ok / approve / tiến hành** → cập nhật plan.md: `Status: PLANNING → IN_PROGRESS`, `Ngày` → hôm nay → tiếp tục Bước 4.
- Nếu user chọn **2 / Chat about** → trả lời câu hỏi / cập nhật plan theo góp ý → hiện lại 2 option trên. Lặp lại cho đến khi user chọn Execute.

---

**Bước 4 — Implement**

Tạo branch `feature/KAN-XX-slug-ngan`. Thực hiện từng Step theo thứ tự:

> Sau mỗi bước hoàn thành:
> `- [ ] Bước N: ...` → `- [x] Bước N: ... — YYYY-MM-DD`
> Cập nhật `Ngày` trong Metadata.

Không bỏ qua bước. Không đánh dấu done khi chưa thực sự xong.

> ⛔ **KHÔNG chạy `git commit` hay `git push` trong `/kltn-task`.**
> Toàn bộ git operations (commit → push → PR) chỉ được thực hiện khi chạy `/kltn-ship KAN-XX`.
