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
```
Từ output ghi nhớ:
- `$ISSUE_NUMBER` — số issue (ví dụ: `12`)
- `$ISSUE_TITLE` — title của issue
- `$SPRINT` — milestone name
- Scope: API mới, chỉnh sửa logic, thêm DB schema, hay tích hợp AI module?
- Input/output của endpoint là gì?
- Cần migration không?

### Bước 2 — Lập Implementation Plan & viết plan.md

Phân tích issue và viết file plan tại `logs/GH-$ISSUE_NUMBER/plan.md`:

```markdown
# Plan — GH-[number]: [Tên issue]

## Metadata
- **Status:** PLANNING
- **Role:** BE | **Ngày:** YYYY-MM-DD
- **Issue:** #[number] — [GitHub URL]
- **Sprint:** [milestone]

## Mục tiêu
[Issue yêu cầu làm gì, endpoint / logic nào]

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| Controllers/XxxController.cs | create/modify | ... |
| Application/Commands/XxxCreate/ | create | ... |

## Approach
[Data flow: request → validation → handler → DB → response]

## Steps
- [ ] Bước 1: [...]
- [ ] Bước 2: [...]
- [ ] Bước 3: [...]
```

> **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi làm bất cứ bước nào tiếp theo.**
> **TUYỆT ĐỐI KHÔNG CODE khi chưa có xác nhận. Không có ngoại lệ, dù issue nhỏ đến đâu.**

### Bước 2.5 — Chọn executor

Sau khi plan được approve, hỏi user:

> **"Ai sẽ thực thi plan này?"**
> 1. **Claude** — Claude Code tự implement (tiếp tục Bước 3 bên dưới)
> 2. **Codex** — Trigger Codex CLI thực thi plan (Claude dừng lại sau bước này)

**Nếu user chọn Option 2 — Codex:**
```bash
codex "Execute the implementation plan in logs/GH-$ISSUE_NUMBER/plan.md.
Follow the coding conventions in .codex/skills/be/ for all patterns (entity, CQRS, controller, migration).
Branch: feature/GH-$ISSUE_NUMBER-$(gh issue view $ISSUE_NUMBER --json title -q '.title' | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-30)
Do not commit or push — stop after implementation."
```

Claude dừng lại sau khi chạy lệnh trên. Codex sẽ tự đọc plan và thực thi.

**Nếu user chọn Option 1 — Claude:** tiếp tục Bước 3 bên dưới.

---

### Bước 3 — Tạo branch
```bash
git checkout -b feature/GH-$ISSUE_NUMBER-ten-tinh-nang
```

### Bước 4 — Implement theo đúng layer (Clean Architecture + CQRS)

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

### Bước 5 — Tự kiểm tra trước commit
- Endpoint cần auth đã có `[Authorize]`
- Role check đúng (Admin / Manager / Staff)
- Không hardcode connection string, secret, URL
- EF Core query không có N+1 (`Include()` đúng chỗ)
- Response không leak field nhạy cảm (password hash, internal ID...)
- Migration có thể rollback an toàn

> ⛔ **KHÔNG commit, KHÔNG push** trong bước này.
> Commit + push + tạo PR chỉ được thực hiện khi chạy `/kltn-ship $ISSUE_NUMBER`.

---

## Không được
- Viết business logic trong Controller
- Gọi DbContext trực tiếp từ Controller hoặc Service
- Hardcode connection string, secret, URL
- Thêm NuGet package chưa có trong tech-defaults
- Tạo migration bằng tay (phải dùng `dotnet ef migrations add`)

---

## Stack BE
ASP.NET Core · EF Core · MediatR (CQRS) · PostgreSQL / TimescaleDB · Redis · JWT Auth · Swagger
Validation: custom `IValidatable<T>` + `ValidateAsync()` — KHÔNG dùng FluentValidation
