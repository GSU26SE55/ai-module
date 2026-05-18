# Hướng dẫn sử dụng hàng ngày — Team GSU26SE55

> Đây là hướng dẫn **sử dụng hàng ngày**. Nếu bạn mới join và cần setup lần đầu, gõ `/kltn-setup`.

---

## GitHub Project — Xem tiến độ Sprint

Toàn bộ task của team được tracking tại:

**https://github.com/orgs/GSU26SE55/projects/3**

### 5 Views có sẵn

| View | Layout | Dùng khi nào |
|------|--------|-------------|
| **Backlog** | Board (group by Status) | Đầu sprint — xem task chưa bắt đầu |
| **Priority board** | Board (group by Priority) | Ưu tiên P1/P2 phải được xử lý trước |
| **Team items** | Table (group by Assignees) | Leader xem ai đang làm gì |
| **Roadmap** | Roadmap (by Milestone) | Xem timeline 8 sprint |
| **My items** | Table (filter: assignee:@me) | Dev xem task của mình mỗi ngày |

### Project Status field vs GitHub Labels

Có **2 hệ thống tracking** chạy song song:

| | GitHub Labels | Project Status field |
|--|--------------|---------------------|
| Giá trị | `status: init/implementing/reviewing/done` | `Backlog / In Progress / Done` |
| Ai cập nhật | `/kltn-*` commands tự động | GitHub Actions tự động (khi label thay đổi) |
| Mục đích | Claude Code workflow | Hiển thị visual trên board |

**Mapping tự động (GitHub Actions):**

| Label | Project Status |
|-------|---------------|
| `status: init` | `Backlog` |
| `status: implementing` | `In Progress` |
| `status: reviewing` | `In Progress` |
| `status: done` | `Done` |

> Issues mới tạo tự động xuất hiện trên board nhờ workflow "Auto-add to project".
> Mỗi issue có nhiều labels đồng thời: `status:` + `role:` + `priority:` + `type:`. Chỉ nhóm `status:` thay đổi theo lifecycle.

---

## Luồng làm việc hàng ngày

> **Issues nằm trong từng sub-repo** — BE dev làm việc trong `backend`, FE dev làm việc trong `frontend`. Sprint Board tổng hợp tất cả.

```
# 0. (Tùy chọn) Tự tạo issue mới nếu phát hiện task chưa được tạo
/kltn-task                 ← Claude hỏi thông tin → xác nhận → tạo issue vào sub-repo
                            ← Issue tự động xuất hiện trên Sprint Board
                            ← Ghi nhớ số issue vừa tạo để dùng ở bước 3

# 1. Xem task được assign
Vào https://github.com/orgs/GSU26SE55/projects/3 → tab "My items"

# 2. cd đúng repo rồi mới mở Claude
cd ~/Documents/GSU26SE55/backend   # (hoặc frontend / mobile / ai-module)
git pull
claude

# 3. Lập plan (bắt buộc trước khi code)
/kltn-plan 12               ← Claude đọc Issue #12
                            ← Claude phân tích gap, hỏi nếu chưa rõ scope/approach
                            ← Claude viết plan.md → logs/GH-12/plan.md
                            ← Bạn review plan → gõ "ok" để xác nhận
                            ← Claude post plan lên Issue comment
                            ← Label tự đổi: status:init → status:implementing
                            ← Sprint Board tự cập nhật: Backlog → In Progress
                            ⚠️  Claude KHÔNG code trước khi có xác nhận

# 4. Implement (sau khi plan approved)
/kltn-implement 12          ← Claude đọc plan.md → bắt đầu code từng bước
                            ← Đánh dấu từng bước hoàn thành trong plan.md

# 5. Code...

# 6. Quality gates
/kltn-reviewcode            ← Claude review diff → PASS hoặc FAIL
/kltn-test 12               ← Claude chạy test → PASS hoặc FAIL

# 7. Ship
/kltn-ship 12               ← Claude tạo PR + comment vào Issue
                            ← Label tự đổi: implementing → reviewing

# 8. Reviewer (đồng đội) chạy
/kltn-reviewpr 12           ← APPROVE hoặc REQUEST CHANGES

# 9. Author chạy sau khi được APPROVE
/kltn-complete 12           ← handoff → merge PR → label: done
                            ← Sprint Board tự cập nhật: In Progress → Done
```

---

## Danh sách lệnh

### Dev (tất cả role)

| Lệnh | Khi nào dùng |
|------|-------------|
| `/kltn-task` | Tạo issue mới vào sub-repo — khi phát hiện task chưa được tạo trong sprint |
| `/kltn-plan 123` | Lập plan cho ticket #123 — đọc issue, hỏi nếu chưa rõ, viết plan, chờ approve |
| `/kltn-implement 123` | Implement — **yêu cầu plan đã approved** (chạy sau `/kltn-plan`) |
| `/kltn-reviewcode` | Review code trước khi test |
| `/kltn-test 123` | Test sau khi reviewcode PASS |
| `/kltn-ship 123` | Tạo PR + cập nhật label → reviewing |
| `/kltn-reviewpr 123` | **[Reviewer]** Review PR → APPROVE hoặc REQUEST CHANGES |
| `/kltn-complete 123` | **[Author]** Sau khi PR APPROVE: handoff → push → merge → done |

### Scaffold BE (tạo boilerplate nhanh)

| Lệnh | Output |
|------|--------|
| `/scaffold-crud {Service} {Entity}` | 16 files + migration |
| `/scaffold-entity {Service} {Entity}` | Entity + DbSet |
| `/scaffold-cqrs-command {Service} {Entity} {Action}` | Command + Handler |
| `/scaffold-cqrs-query {Service} {Entity} GetList\|GetById` | Query + Handler |
| `/scaffold-controller {Service} {Entity}` | Controller |
| `/scaffold-consumer {Service} {EventName}` | RabbitMQ Consumer |
| `/scaffold-unit-tests {Service} {Entity}` | Unit tests |
| `/run-migration {Service} {MigrationName}` | EF migration |

### Scaffold AI

| Lệnh | Output |
|------|--------|
| `/scaffold-fastapi-endpoint {name}` | FastAPI router + Pydantic schema |

### Leader only

| Lệnh | Tác dụng |
|------|---------|
| `/kltn-sprint` | Lên kế hoạch sprint — tạo GitHub Issues trong sub-repos, phân công assignee |
| `/kltn-team` | Báo cáo tiến độ toàn team theo GitHub labels |
| `/kltn-member [tên]` | Check tiến độ từng người theo Issues được assign |

### MCP tools

```
# Context7 — tra docs thư viện
dùng context7 tìm cách dùng IMediator trong MediatR .NET
dùng context7 tìm cách dùng useMutation trong TanStack Query v5
```

---

## RTK — Token Saver

RTK chạy tự động nhờ global hook trong `~/.claude/settings.json` — khi Claude Code gọi bất kỳ lệnh Bash nào, hook tự wrap qua `rtk` trước khi thực thi, không cần làm gì thêm.

> Nếu bạn mới setup máy và chưa có hook này: xem Bước 5 trong `/kltn-setup`.

**Khi bạn tự gõ lệnh trong terminal** (ngoài Claude Code), thêm `rtk` prefix để tiết kiệm token tương tự:

| Lệnh | Thay vì | Tiết kiệm |
|------|---------|-----------|
| `rtk git diff` | `git diff` | ~80% |
| `rtk git log` | `git log` | ~70% |
| `rtk gh issue list` | `gh issue list` | ~80% |
| `rtk gh pr view 42` | `gh pr view 42` | ~87% |
| `rtk dotnet build` | `dotnet build` | ~80% |
| `rtk pytest tests/` | `pytest tests/` | ~90% |
| `rtk tsc --noEmit` | `tsc --noEmit` | ~83% |

**Xem thống kê tiết kiệm:**
```bash
rtk gain           # tổng token đã tiết kiệm
rtk gain --history # lịch sử theo lệnh
```

---

## Definition of Done

Ticket chỉ được coi là **Done** khi đủ cả 3:

1. `/kltn-reviewcode` → **PASS**
2. `/kltn-test` → **PASS**
3. PR được ≥ 1 người approve và **merged vào dev**

---

## Quy tắc bắt buộc

- **Không merge PR của chính mình** — cần ít nhất 1 người approve
- **Không push thẳng lên dev** — luôn qua PR
- **1 issue = 1 branch** — `feature/GH-[number]-ten-ngan` (ví dụ: `feature/GH-42-battery-crud`)
- **Commit format:** `feat(#42): mô tả` / `fix(#42)` / `refactor(#42)` / `test(#42)`
- **PR body phải có** `Closes #[number]` — GitHub tự close issue khi merge
- **Không commit** `CLAUDE.local.md` — đã có trong `.gitignore`
- **Không tự thêm package** ngoài stack trong `rules/tech/` — hỏi Leader trước

---

## Label hệ thống

Mỗi issue mang nhiều labels đồng thời:

| Nhóm | Labels |
|------|--------|
| **Status** | `status: init` · `status: implementing` · `status: reviewing` · `status: done` |
| **Role** | `role: BE` · `role: FE` · `role: Mobile` · `role: AI` |
| **Priority** | `priority: P1: Critical (4h)` · `priority: P2: High (24h)` · `priority: P3: Standard (72h)` |
| **Type** | `type: feat` · `type: fix` · `type: refactor` · `type: test` · `type: docs` · `type: chore` |

Ví dụ issue mới được tạo sẽ có: `status: init` + `role: BE` + `priority: P2: High (24h)` + `type: feat`

---

## Cập nhật config / skills

> Mọi thay đổi `.claude/` phải đi qua `workflow-ai` → Leader review → mới sync xuống.
> **Không sửa trực tiếp trong role repo** — sẽ bị ghi đè khi Actions sync.

### Member — đề xuất thay đổi

```bash
git clone https://github.com/GSU26SE55/workflow-ai.git && cd workflow-ai
git checkout -b fix/ten-thay-doi
# Sửa file trong .claude/
git add .claude/
git commit -m "fix: mô tả thay đổi"
git push origin fix/ten-thay-doi
# Mở PR → assign Leader review
```

### Leader — sync config xuống sub-repos

```bash
cd workflow-ai
git checkout -b chore/ten-thay-doi
git add .claude/
git commit -m "chore: mô tả thay đổi"
git push origin chore/ten-thay-doi
# Mở PR → self-merge sau khi verify
```

> **Lưu ý:** pre-commit hook chặn commit thẳng lên `main` của `workflow-ai` — Leader cũng phải tạo branch và PR.

Theo dõi Actions tại: https://github.com/GSU26SE55/workflow-ai/actions

---

## Cần hỗ trợ

Liên hệ Leader: **Trần Minh Trí (SE183109)**
