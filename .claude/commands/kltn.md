Hiển thị toàn bộ commands và hướng dẫn sử dụng hàng ngày của dự án GSU26SE55.

Đọc CLAUDE.local.md để xác định role, sau đó in toàn bộ nội dung bên dưới:

---

## KLTN Commands — GSU26SE55

### Setup

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-setup` | Mới join project — chạy 1 lần duy nhất |
| `/kltn` | Hiện menu này + hướng dẫn hàng ngày |

---

### Dev Commands (tất cả thành viên)

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-task` | Tạo GitHub Issue mới vào sub-repo (skeleton — context sẽ post sau khi plan) |
| `/kltn-plan GH-XX` | Hiểu rõ task — đọc issue, hỏi nếu chưa rõ, lập plan, chờ approve |
| `/kltn-implement GH-XX` | Implement — **yêu cầu plan đã approved** |
| `/kltn-reviewcode` | Review code trước khi ship — xuất PASS / FAIL |
| `/kltn-test GH-XX` | Kiểm thử sau khi reviewcode PASS — xuất PASS / FAIL |
| `/kltn-ship GH-XX` | Tạo PR + handoff file + cập nhật label → reviewing |
| `/kltn-complete GH-XX` | Sau khi PR APPROVE trên GitHub: merge → done (chỉ author) |
| `/kltn-debug GH-XX` | Fix bug từ issue log sheet — detect branch, đọc lỗi, fix, push |

**Luồng chuẩn (bắt buộc với MỌI task):**
```
[Author]   /kltn-task            → tạo issue mới (nếu chưa có)
[Author]   /kltn-plan GH-XX      → đọc issue → hỏi nếu chưa rõ → plan.md → approve
[Author]   /kltn-implement GH-XX → implement từng bước trong plan
           → /kltn-reviewcode → /kltn-test GH-XX → /kltn-ship GH-XX
[Reviewer] review PR trực tiếp trên GitHub → APPROVE hoặc REQUEST CHANGES
[Author]   /kltn-complete GH-XX  → merge → Done
```

**Ví dụ thực tế (issue #42):**
```
/kltn-task          ← tạo issue #42 (nếu chưa có)
/kltn-plan 42       ← đọc issue, hỏi nếu scope/approach chưa rõ, tạo plan
/kltn-implement 42  ← implement theo plan đã approve
/kltn-ship 42       ← tạo PR + handoff file, label → reviewing
                    ← reviewer xem PR trên GitHub và approve
/kltn-complete 42   ← merge PR, label → done
```

---

### Scaffold BE (tạo boilerplate nhanh)

| Lệnh | Output |
|------|--------|
| `/scaffold-crud {Service} {Entity}` | 16 files + migration (full CRUD) |
| `/scaffold-entity {Service} {Entity}` | Entity + DbSet |
| `/scaffold-dto {Service} {Entity}` | DTO + Response wrappers |
| `/scaffold-cqrs-command {Service} {Entity} {Action}` | Command + Handler |
| `/scaffold-cqrs-query {Service} {Entity} GetList\|GetById` | Query + Handler |
| `/scaffold-controller {Service} {Entity}` | Controller |
| `/scaffold-consumer {Service} {EventName}` | RabbitMQ Consumer |
| `/scaffold-integration-event {EventName}` | Integration event record |
| `/scaffold-unit-tests {Service} {Entity}` | Unit tests |
| `/run-migration {Service} {MigrationName}` | EF migration |

### Scaffold AI

| Lệnh | Output |
|------|--------|
| `/scaffold-fastapi-endpoint {name}` | FastAPI router + Pydantic schema |

### Leader Commands (chỉ Trần Minh Trí — SE183109)

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-sprint` | Đầu sprint — tạo GitHub Issues trong sub-repos, phân công assignee |
| `/kltn-team` | Báo cáo tiến độ toàn team |
| `/kltn-member [tên]` | Check tiến độ từng người cụ thể |

---

## Hướng dẫn hàng ngày

### GitHub Project — Xem tiến độ Sprint

**https://github.com/orgs/GSU26SE55/projects/3**

| View | Layout | Dùng khi nào |
|------|--------|-------------|
| **Backlog** | Board (group by Status) | Đầu sprint — xem task chưa bắt đầu |
| **Priority board** | Board (group by Priority) | Ưu tiên P1/P2 phải được xử lý trước |
| **Team items** | Table (group by Assignees) | Leader xem ai đang làm gì |
| **Roadmap** | Roadmap (by Milestone) | Xem timeline 8 sprint |
| **My items** | Table (filter: assignee:@me) | Dev xem task của mình mỗi ngày |

**Label → Project Status (GitHub Actions tự động sync):**

| Label | Project Status |
|-------|---------------|
| `status: init` | Backlog |
| `status: implementing` | In Progress |
| `status: reviewing` | In Progress |
| `status: done` | Done |

---

### Luồng hàng ngày

```
# 0. (Tùy chọn) Tạo issue mới nếu task chưa có trên board
/kltn-task         ← nhập tiêu đề, type, priority → issue tự lên Sprint Board

# 1. Xem task được assign
Vào https://github.com/orgs/GSU26SE55/projects/3 → tab "My items"

# 2. cd đúng repo rồi mới mở Claude
cd ~/Documents/GSU26SE55/backend   # (hoặc frontend / mobile / ai-module)
git pull
claude

# 3. Lập plan (bắt buộc trước khi code)
/kltn-plan 12      ← Claude đọc issue, phân tích gap, hỏi nếu chưa rõ
                   ← Claude viết plan.md → logs/GH-12/plan.md
                   ← Bạn review plan → gõ "ok" để xác nhận
                   ← Claude post plan lên Issue + label: init → implementing
                   ⚠️  Claude KHÔNG code trước khi có xác nhận

# 4. Implement
/kltn-implement 12 ← Claude đọc plan.md → code từng bước

# 5. Quality gates
/kltn-reviewcode   ← Claude review diff → PASS hoặc FAIL
/kltn-test 12      ← Claude chạy test → PASS hoặc FAIL

# 6. Ship
/kltn-ship 12      ← Claude tạo PR + comment vào Issue
                   ← Label: implementing → reviewing

# 7. Reviewer xem PR trên GitHub và approve (không cần dùng claude)

# 8. Author chạy sau khi được APPROVE
/kltn-complete 12  ← merge PR → label: done
```

---

### MCP Tools

```
# Context7 — tra docs thư viện
dùng context7 tìm cách dùng IMediator trong MediatR .NET
dùng context7 tìm cách dùng useMutation trong TanStack Query v5
```

---

### Definition of Done

Ticket được coi là **Done** khi **đủ cả 3**:
1. `/kltn-reviewcode` → PASS
2. `/kltn-test GH-XX` → PASS
3. PR được ≥ 1 người approve và merged vào dev

---

### Quy tắc bắt buộc

- Không push thẳng lên `dev` — luôn qua PR
- Không merge PR của chính mình — cần ít nhất 1 người approve
- Branch theo type: `feat/GH-[number]-slug` (feature) · `fix/GH-[number]-slug` (bug fix) · `chore/[purpose]` · `docs/[purpose]` · `refactor/[purpose]` · `test/[purpose]`
- 1 issue = 1 branch, merge chỉ qua PR vào `dev`
- Commit format: `feat(#42): mô tả` / `fix(#42)` / `refactor(#42)` / `test(#42)`
- PR body phải có `Closes #[number]` để GitHub tự close issue khi merge
- Không commit `CLAUDE.local.md` — đã có trong `.gitignore`
- Không thêm package ngoài tech stack trong `.claude/rules/tech/{be,fe,mobile,ai}.md`

---

### Label hệ thống

| Nhóm | Labels |
|------|--------|
| **Status** | `status: init` · `status: implementing` · `status: reviewing` · `status: done` |
| **Role** | `role: BE` · `role: FE` · `role: Mobile` · `role: AI` |
| **Priority** | `priority: P1: Critical (4h)` · `priority: P2: High (24h)` · `priority: P3: Standard (72h)` |
| **Type** | `type: feat` · `type: fix` · `type: refactor` · `type: test` · `type: docs` · `type: chore` |

---

### Cập nhật config / skills

> Mọi thay đổi `.claude/` phải đi qua `workflow-ai` → Leader review → mới sync xuống.
> **Không sửa trực tiếp trong role repo** — sẽ bị ghi đè khi Actions sync.

```bash
# Member — đề xuất thay đổi
git clone https://github.com/GSU26SE55/workflow-ai.git && cd workflow-ai
git checkout -b fix/ten-thay-doi
# Sửa file trong .claude/
git commit -m "fix: mô tả thay đổi"
git push origin fix/ten-thay-doi
# Mở PR → assign Leader review
```

Theo dõi Actions tại: https://github.com/GSU26SE55/workflow-ai/actions

Cần hỗ trợ: **Trần Minh Trí (SE183109)**
