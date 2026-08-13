# Skill: /kltn-implement (BE)

## Kích hoạt
`/kltn-implement [issue-number]` — làm việc trên GitHub Issue phía Backend.

---

## Quy trình

### Bước 0 — Kiểm tra CLAUDE.local.md
```bash
cat .claude/CLAUDE.local.md 2>/dev/null || { echo "❌ CLAUDE.local.md chưa tồn tại — tạo file này trước (xem /kltn-setup)"; exit 1; }
```
Xác nhận file có đủ 4 trường: **Tên**, **MSSV**, **Role chính**, **Role phụ**.
Nếu thiếu → dừng lại và yêu cầu tạo/bổ sung trước khi tiếp tục.

### Bước 1 — Đọc GitHub Issue
```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels,milestone,assignees

# Đọc sub-issues (nếu có)
gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/issues/$ISSUE_NUMBER/sub_issues \
  --jq '.[] | {number: .number, title: .title, body: .body, state: .state}'
```
Từ output ghi nhớ:
- `$ISSUE_NUMBER` — số issue (ví dụ: `12`)
- `$ISSUE_TITLE` — title của issue
- `$SPRINT` — milestone name
- Scope: API mới, chỉnh sửa logic, thêm DB schema, hay tích hợp AI module?
- Input/output của endpoint là gì?
- Cần migration không?
- Tổng hợp thêm context từ sub-issues nếu có.

### Bước 2 — Kiểm tra plan hiện tại

```bash
cat logs/GH-$ISSUE_NUMBER/plan.md 2>/dev/null
```

- **Nếu tồn tại** → Hiện nội dung, hỏi:
  ```
  Plan đã tồn tại (Status: [status]).
  [1] Dùng plan này → tiếp tục Bước 2.5
  [2] Ghi đè plan mới → tiếp tục viết plan bên dưới
  ```
  Chờ user chọn. Nếu chọn 1 → chuyển thẳng sang Bước 2.5.

- **Nếu chưa tồn tại** → Lập plan và viết file tại `logs/GH-$ISSUE_NUMBER/plan.md`:

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING
- **Role:** BE | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [GitHub URL]
- **Sprint:** [milestone]

## Mục tiêu
[Issue yêu cầu làm gì, endpoint / logic nào]

## Scope
- Trong scope: ...
- Ngoài scope: ...

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| Controllers/XxxController.cs | create/modify | ... |
| Application/Commands/XxxCreate/ | create | ... |

## Approach
[Data flow: request → validation → handler → DB → response]

## Edge Cases
- Input không hợp lệ: ...
- Error handling: ...

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| [Mô tả outcome cụ thể] | [Lệnh / bước kiểm tra] |

## Steps
- [ ] Bước 1: [...]
- [ ] Bước 2: [...]
- [ ] Bước 3: [...]

## Câu hỏi đã giải đáp
[Tóm tắt những điểm đã hỏi và câu trả lời — để reviewer hiểu context]
```

> **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "yes", "y", "tiến hành") trước khi làm bất cứ bước nào tiếp theo.**
> **TUYỆT ĐỐI KHÔNG CODE khi chưa có xác nhận. Không có ngoại lệ, dù issue nhỏ đến đâu.**

### Bước 2.5 — Chọn executor

Sau khi plan được approve, hỏi user:

> **"Ai sẽ thực thi plan này?"**
> 1. **Claude** — Claude Code tự implement (tiếp tục Bước 3 bên dưới)
> 2. **Codex** — Sinh description để paste vào Codex CLI (Claude dừng lại sau bước này)

**Nếu user chọn Option 2 — Codex:**

Claude đọc toàn bộ `logs/GH-$ISSUE_NUMBER/plan.md`, tính slug từ title issue, rồi in ra description kèm hướng dẫn rõ ràng:

---

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 CODEX DESCRIPTION — GH-$ISSUE_NUMBER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👉 Thực hiện theo thứ tự:
   1. Mở terminal (hoặc cửa sổ Codex CLI bạn đang dùng)
   2. cd vào đúng thư mục repo:
        cd ~/Documents/GSU26SE55/backend
   3. Copy TOÀN BỘ đoạn bên dưới (từ dòng "You are..." đến hết "...clearly.")
   4. Paste vào Codex CLI và nhấn Enter
   5. Codex tự chạy — không cần làm gì thêm

⚠️  Lưu ý:
   - Copy đúng toàn bộ, không bỏ sót dòng nào
   - Codex sẽ KHÔNG commit / push — chỉ implement code
   - Sau khi Codex xong → quay lại chạy /kltn-reviewcode $ISSUE_NUMBER

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✂️  COPY TỪ ĐÂY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are implementing GitHub Issue #$ISSUE_NUMBER for a Backend (ASP.NET Core / Clean Architecture / CQRS) project.

Follow ALL coding conventions in .codex/skills/be/ (entity, CQRS commands/queries, controller, migration, custom IValidatable<T>).

Branch to create: feat/GH-$ISSUE_NUMBER-$SLUG

== IMPLEMENTATION PLAN ==
[toàn bộ nội dung logs/GH-$ISSUE_NUMBER/plan.md được paste ở đây]
== END OF PLAN ==

Rules:
- Follow the Steps section in order, check off each step as done.
- Do NOT commit or push — stop after implementation.
- If a step fails, stop and report the error clearly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✂️  COPY ĐẾN ĐÂY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

> Claude dừng lại sau khi in description. Chờ user thực hiện xong với Codex rồi tiếp tục `/kltn-reviewcode $ISSUE_NUMBER`.

**Nếu user chọn Option 1 — Claude:** tiếp tục Bước 3 bên dưới.

---

### Bước 3 — Tạo branch
```bash
# Slug: viết thường, chỉ a-z/0-9/gạch ngang, tối đa 5 từ
# Ví dụ: "Add Battery CRUD API" → feat/GH-42-add-battery-crud-api
SLUG=$(gh issue view $ISSUE_NUMBER --json title -q '.title' \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs 'a-z0-9' '-' \
  | tr -s '-' \
  | cut -d'-' -f1-5 \
  | sed 's/-$//')

git checkout -b feat/GH-$ISSUE_NUMBER-$SLUG
```

### Bước 4 — Implement theo đúng layer (Clean Architecture + CQRS)

> Nếu `.claude/skills/dev/be/implement/SKILL.md` tồn tại → đọc trước khi code. Nếu không tồn tại → tiếp tục theo plan.md, không dừng.

```
Api/Controllers/      ← nhận request, gọi _mediator.Send() → KHÔNG chứa logic
Application/Commands/ ← CommandHandler: inject IUnitOfWork, chứa business logic
Application/Queries/  ← QueryHandler: inject IUnitOfWork, truy vấn read-only
Application/DTOs/     ← DTO + ValidateAsync() (custom IValidatable<T>, KHÔNG dùng FluentValidation)
Domain/Entities/      ← extend AuditableEntity, ZERO dependency
Infrastructure/       ← GenericRepository, DbContext, Consumers, DI
Migrations/           ← chỉ tạo qua: dotnet ef migrations add
```

**Khi nào dùng TimescaleDB vs PostgreSQL:**
- Sensor readings, time-series data → **TimescaleDB**
- Users, tickets, configs → **PostgreSQL thường**

**Khi nào dùng Redis:**
- Session / auth token cache
- Pub/sub cho real-time alert

Thực hiện từng Step trong `plan.md` theo thứ tự:

> Sau mỗi bước hoàn thành:
> `- [ ] Bước N: ...` → `- [x] Bước N: ... — YYYY-MM-DD`
> Cập nhật `Ngày` trong Metadata.

Không bỏ qua bước. Không đánh dấu done khi chưa thực sự xong.

> Nếu một bước thất bại (build error, migration conflict, test fail…) → **dừng ngay**, báo lỗi cụ thể cho user, không tự ý skip hoặc workaround mà không hỏi.

### Bước 5 — Tự kiểm tra trước commit
- Endpoint cần auth đã có `[Authorize]`
- Role check đúng (Admin / Manager / Staff)
- Không hardcode connection string, secret, URL
- EF Core query không có N+1 (`Include()` đúng chỗ)
- Response không leak field nhạy cảm (password hash, internal ID...)
- Migration có thể rollback an toàn
- Validation dùng custom `IValidatable<T>` + `ValidateAsync()`, không dùng FluentValidation
- Không gọi DbContext trực tiếp từ Controller hoặc Handler — phải qua `IUnitOfWork`
- Migration tạo bằng `dotnet ef migrations add`, không viết tay

Sau khi tất cả checklist pass → cập nhật `plan.md`: `Status: IN_PROGRESS → REVIEWING`.

> ⛔ **KHÔNG commit, KHÔNG push** trong bước này.
> Commit + push + tạo PR chỉ được thực hiện khi chạy `/kltn-ship $ISSUE_NUMBER`.

---

## Sau khi implement xong — chạy theo thứ tự

```
/kltn-reviewcode  →  /kltn-test  →  /kltn-ship $ISSUE_NUMBER
```

---

## Không được
- Viết business logic trong Controller
- Gọi DbContext trực tiếp từ Controller hoặc Service
- Hardcode connection string, secret, URL
- Thêm NuGet package chưa có trong tech-defaults
- Tạo migration bằng tay (phải dùng `dotnet ef migrations add`)
- Dùng FluentValidation — chỉ dùng custom `IValidatable<T>`

---

## Stack BE
ASP.NET Core · EF Core · MediatR (CQRS) · PostgreSQL / TimescaleDB · Redis · JWT Auth · Swagger
Validation: custom `IValidatable<T>` + `ValidateAsync()` — KHÔNG dùng FluentValidation
