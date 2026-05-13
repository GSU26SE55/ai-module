# Claude Agent System —GSU26SE55

Hệ thống agent hỗ trợ dự án Capstone **Solar Lithium-ion Battery Maintenance Management System** — nghiên cứu kỹ thuật, theo dõi tiến độ team, và hỗ trợ phát triển phần mềm.

---

## Ngữ cảnh dự án

**Dự án:** Nền tảng AI giám sát và bảo trì pin lithium-ion cho hệ thống năng lượng mặt trời.
**Nhóm:** 5 sinh viên (3 BE + 2 FE) — GVHD: Trương Long
**Timeline:** 8 sprint, từ 11/5/2026 → 6/9/2026

**Hệ thống gồm 3 phần:**
- Mobile App (React Native/Expo) — giám sát pin real-time, Customer dùng
- Web App (ReactJS) — quản lý Admin/Manager/Staff + SLA ticket theo ITIL
- AI Module (FastAPI + PyTorch) — phân loại trạng thái pin, dự đoán SOH bằng LSTM/CNN-LSTM

> Core business flow (4 role · 6 phase · ticket state machine · SLA): [docs/core-business-flow.md](docs/core-business-flow.md)
> Chi tiết đầy đủ xem tại: [memory.md](memory.md)

---

## Microservices BE

| Service | Chức năng chính | Ghi chú |
|---------|----------------|---------|
| UserService | Auth (JWT/refresh), User CRUD, role management, OTP activate | Phát sinh `UserCreatedEvent` |
| BatteryService | Battery CRUD, sensor readings (TimescaleDB), threshold config, assign cho Customer | Phát sinh `BatteryAnomalyDetectedEvent` |
| TicketService | Ticket lifecycle, SLA timer, maintenance log, comment, escalation | Consume `BatteryAnomalyDetectedEvent` để auto-tạo ticket |
| NotificationService | Push notification (Expo), email (invite/reset/alert) | Consume các event từ services khác |

**Ticket states:** `NEW → OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED_PENDING_RATE → CLOSED`
Ngoài ra: `ESCALATED` (từ P1/P2 breach hoặc Staff request) · `CLOSED_REJECTED` (Manager từ chối ngoài scope)

**SLA theo priority (Manager gán, không thay đổi trong vòng đời ticket):**
- P1 Critical: 4h · P2 High: 24h · P3 Standard: 72h

---

## Cấu trúc hệ thống

```
.codex/
└── skills/                ← codex skills (dùng bởi Codex CLI, không phải Claude Code)
    ├── be/
    │   ├── entity/SKILL.md          ← Entity scaffold
    │   ├── controller/SKILL.md
    │   ├── cqrs-command/SKILL.md
    │   ├── cqrs-query/SKILL.md
    │   ├── consumer/SKILL.md
    │   └── migration/SKILL.md
    ├── fe/
    │   ├── feature/SKILL.md         ← Feature module pattern
    │   └── hook/SKILL.md            ← TanStack Query hook pattern
    └── ai/
        └── fastapi-endpoint/SKILL.md

.claude/
├── CLAUDE.md              ← file này — bộ não dự án
├── CLAUDE.local.md        ← ghi chú cá nhân, không push lên Git
├── settings.json          ← permissions + hooks (commit được)
├── settings.local.json    ← permissions + hooks private (không commit)
├── memory.md              ← thông tin dự án chi tiết
├── hooks/                 ← safety gates + quality checks theo role
│   ├── be/                         ← hooks cho BE role repo (.cs files)
│   │   ├── block-dangerous-commands.sh ← BLOCK rm -rf, force push, DROP DB
│   │   ├── protect-sensitive-files.sh  ← BLOCK edit .env, credentials
│   │   ├── check-build.sh              ← dotnet build sau mỗi lần edit .cs
│   │   ├── post-edit-feedback.sh       ← warn anti-patterns (await void, fat controller)
│   │   ├── validate-namespace.sh       ← warn namespace mismatch
│   │   ├── check-di-registration.sh    ← remind đăng ký DI
│   │   └── check-dbcontext-update.sh   ← remind DbSet + migration khi tạo entity
│   ├── fe/                         ← hooks cho FE role repo (.ts/.tsx files)
│   │   ├── check-build.sh              ← tsc --noEmit sau mỗi lần edit .ts/.tsx
│   │   └── post-edit-feedback.sh       ← warn console.log, localStorage, cross-feature import
│   └── ai/                         ← hooks cho AI role repo (.py files)
│       ├── check-ruff.sh               ← ruff lint + format sau mỗi lần edit .py
│       └── check-random-seed.sh        ← warn nếu training script thiếu random seed
├── docs/
│   ├── guide.md
│   ├── core-business-flow.md
│   ├── ai-datasets.md              ← download links + convention cho 4 datasets
│   └── ai-research-references.md   ← tài liệu nghiên cứu AI tham khảo
├── rules/                 ← quy tắc — mọi người đều follow
│   ├── workflow.md        ← quy trình làm việc & git flow
│   ├── design.md          ← kiến trúc hệ thống 3-layer
│   └── tech/
│       ├── be.md          ← BE rules đầy đủ (15 rules, load khi edit .cs)
│       ├── fe.md          ← FE rules
│       ├── mobile.md      ← Mobile rules
│       └── ai.md          ← AI rules
├── agents/                ← sub-agent chuyên dụng (leader dùng)
│   ├── researcher.md      ← thu thập & tổng hợp thông tin
│   ├── reviewer.md        ← kiểm tra chất lượng & khuyến nghị
│   ├── tester.md          ← kiểm thử BE/FE/Mobile/AI trước khi merge
│   └── debugger.md        ← debug có cấu trúc 6-phase (reproduce → fix → verify)
└── skills/
    ├── leader/            ← CHỈ LEADER dùng
    │   ├── review-team/SKILL.md   ← /kltn-team    — tracking toàn team
    │   ├── sprint-plan/SKILL.md   ← /kltn-sprint  — lên kế hoạch sprint
    │   └── member-status/SKILL.md ← /kltn-member  — check từng người
    └── dev/
        ├── be/            ← BE Dev dùng
        │   ├── implement/SKILL.md             ← /kltn-implement [issue-number]
        │   ├── code-review/SKILL.md           ← /kltn-reviewcode
        │   ├── test/SKILL.md                  ← /kltn-test [issue-number]
        │   ├── ship/SKILL.md                  ← /kltn-ship [issue-number]
        │   ├── review-pr/SKILL.md             ← /kltn-reviewpr [issue-number]
        │   ├── scaffold-entity/SKILL.md       ← /scaffold-entity Service Entity
        │   ├── scaffold-dto/SKILL.md          ← /scaffold-dto Service Entity
        │   ├── scaffold-cqrs-command/SKILL.md ← /scaffold-cqrs-command Service Entity Action
        │   ├── scaffold-cqrs-query/SKILL.md   ← /scaffold-cqrs-query Service Entity GetList|GetById
        │   ├── scaffold-controller/SKILL.md   ← /scaffold-controller Service Entity
        │   ├── scaffold-crud/SKILL.md         ← /scaffold-crud Service Entity (full CRUD)
        │   ├── run-migration/SKILL.md         ← /run-migration Service MigrationName
        │   ├── scaffold-consumer/SKILL.md     ← /scaffold-consumer Service EventName
        │   ├── scaffold-integration-event/SKILL.md ← /scaffold-integration-event EventName
        │   └── scaffold-unit-tests/SKILL.md   ← /scaffold-unit-tests Service Entity
        ├── fe/            ← FE Dev dùng
        │   ├── implement/SKILL.md   ← /kltn-implement [issue-number]
        │   ├── code-review/SKILL.md ← /kltn-reviewcode
        │   ├── test/SKILL.md        ← /kltn-test [issue-number]
        │   ├── ship/SKILL.md        ← /kltn-ship [issue-number]
        │   └── review-pr/SKILL.md   ← /kltn-reviewpr [issue-number]
        ├── ai/            ← AI Dev dùng
        │   ├── implement/SKILL.md, code-review/SKILL.md, test/SKILL.md, ship/SKILL.md, review-pr/SKILL.md
        │   └── scaffold-fastapi-endpoint/SKILL.md ← /scaffold-fastapi-endpoint <name>
        └── task/SKILL.md                      ← /kltn-task (tất cả role)
```

---

## Phân công Role

Mỗi thành viên có **1 role chính** và các **role phụ**. AI là role phụ chung toàn team.
Danh sách đầy đủ (MSSV, GitHub username): xem [memory.md](memory.md#roster-team).

Khai báo trong `CLAUDE.local.md` (không commit):
```
Role chính: BE        ← dùng skills/dev/be/
Role phụ:   FE, AI    ← có thể dùng skills/dev/fe/ và skills/dev/ai/
```

---

## Phân quyền sử dụng

> ✅ = dùng được | 🔶 = dùng khi làm task role phụ | ❌ = không dùng

| | Leader | BE chính | FE chính | Ghi chú |
|--|--------|----------|----------|---------|
| **rules/** (đọc) | ✅ | ✅ | ✅ | Mọi người đọc tất cả |
| `/kltn-implement` | ✅ | ✅ | ✅ | Theo role của ticket |
| `/kltn-reviewcode` | ✅ | ✅ | ✅ | Theo role của ticket |
| `/kltn-test` | ✅ | ✅ | ✅ | Không dùng Playwright/screenshot |
| `/kltn-ship` | ✅ | ✅ | ✅ | |
| `/kltn-reviewpr` | ✅ | ✅ | ✅ | Reviewer chạy — chỉ approve/request-changes |
| `/kltn-complete` | ✅ | ✅ | ✅ | Author chạy sau khi PR được approve |
| `/kltn-task` | ✅ | ✅ | ✅ | Tạo issue mới vào sub-repo của mình |
| `/scaffold-crud` | ✅ | ✅ | 🔶 | FE dùng khi làm task BE phụ |
| `/scaffold-entity` | ✅ | ✅ | 🔶 | |
| `/scaffold-cqrs-command` | ✅ | ✅ | 🔶 | |
| `/scaffold-cqrs-query` | ✅ | ✅ | 🔶 | |
| `/scaffold-controller` | ✅ | ✅ | 🔶 | |
| `/scaffold-consumer` | ✅ | ✅ | 🔶 | |
| `/scaffold-integration-event` | ✅ | ✅ | 🔶 | |
| `/scaffold-unit-tests` | ✅ | ✅ | 🔶 | |
| `/run-migration` | ✅ | ✅ | 🔶 | |
| `/scaffold-fastapi-endpoint` | ✅ | 🔶 | 🔶 | AI phụ — ai cũng dùng được |
| `/kltn-team` | ✅ | ❌ | ❌ | Chỉ Leader |
| `/kltn-sprint` | ✅ | ❌ | ❌ | Chỉ Leader |
| `/kltn-member` | ✅ | ❌ | ❌ | Chỉ Leader |
| **agents/** | ✅ | ❌ | ❌ | Chỉ Leader |

---

## Memory Hierarchy

Dự án áp dụng chuẩn hierarchical CLAUDE.md loading của Claude Code:

```
sub-repo/
├── CLAUDE.md              ← component-level (role-specific quick ref) — lazy load
└── .claude/
    ├── CLAUDE.md          ← project brain (file này) — luôn load khi start
    ├── memory.md          ← ngữ cảnh bổ sung (timeline, datasets)
    └── rules/tech/be.md   ← full rules — load khi cần
```

| Cấp | File | Load khi nào | Nội dung |
|-----|------|-------------|----------|
| Global | `~/.claude/CLAUDE.md` | Luôn luôn | Personal prefs |
| Project | `.claude/CLAUDE.md` (file này) | Luôn luôn | Project brain |
| Component | `sub-repo/CLAUDE.md` | Luôn luôn khi chạy từ sub-repo | Role quick ref |
| Personal | `.claude/CLAUDE.local.md` | Luôn luôn, không commit | Role cá nhân |

Templates component CLAUDE.md: `templates/{backend|frontend|ai-module|mobile}/CLAUDE.md`
Leader sync về sub-repo qua `bash push-config.sh` (push workflow-ai lên org, GitHub Action tự sync xuống role repos) + `push-to-org.sh` (templates).

---

## Nguyên tắc hoạt động

- **Rules** — quy tắc bất biến, không ai được bỏ qua khi code
- **Dev workflow** — quy trình chuẩn: (tùy chọn: `/kltn-task` tạo task mới) → `/kltn-plan` → `/kltn-implement` → code → `/kltn-reviewcode` → `/kltn-test` → `/kltn-ship` → [reviewer] `/kltn-reviewpr` → [author] `/kltn-complete`
- **BE scaffold** — tạo boilerplate nhanh: `/scaffold-crud Service Entity` (full CRUD 1 lệnh)
- **Leader skills** — tracking và planning, không can thiệp vào flow coding của dev
- **Hooks** — tự động chạy sau mỗi edit .cs: build check, namespace validate, anti-pattern warning
- **RTK** — global hook trong `~/.claude/settings.json` tự động wrap mọi lệnh Bash qua `rtk` trước khi chạy; giảm 60–90% token. Mọi thành viên phải chạy `rtk init -g --auto-patch` 1 lần sau khi cài RTK (xem `docs/setup.md`)
- **Log files** — `/kltn-reviewcode` ghi `logs/GH-[number]/review.md`, `/kltn-test` ghi `logs/GH-[number]/test.md`; `/kltn-ship` commit cả folder `logs/GH-[number]/` lên branch trước khi tạo PR; `/kltn-complete` tạo `logs/GH-[number]/handoff.md` rồi push → merge
- Sprint plan và leader report (`/kltn-team`, `/kltn-member`) xuất trong conversation — không lưu file

### Lệnh kltn — tất cả role

| Lệnh | Ai dùng | Tác dụng |
|------|---------|---------|
| `/kltn-task` | Dev | Tạo GitHub Issue mới vào sub-repo (skeleton, chưa cần plan) |
| `/kltn-plan 123` | Dev | Đọc issue → phân tích gap → hỏi nếu chưa rõ → viết plan.md → chờ approve → post lên issue |
| `/kltn-implement 123` | Dev | Implement — **yêu cầu plan đã approved** (chạy sau `/kltn-plan`) |
| `/kltn-reviewcode` | Dev | Review diff — PASS / FAIL |
| `/kltn-test 123` | Dev | Chạy test — PASS / FAIL |
| `/kltn-ship 123` | Dev | Tạo PR + label → reviewing |
| `/kltn-reviewpr 123` | Reviewer | Review PR → APPROVE / REQUEST CHANGES |
| `/kltn-complete 123` | Author | Merge PR + label → done |
| `/kltn-sprint` | **Leader** | Lên kế hoạch sprint — tạo issues + phân công |
| `/kltn-team` | **Leader** | Báo cáo tiến độ toàn team |
| `/kltn-member [tên]` | **Leader** | Check tiến độ từng người |

## BE Scaffold Workflow (mới)

```
Nhận ticket cần thêm entity mới:
1. /scaffold-crud BatteryService Battery     ← tạo 16 files + migration
   hoặc từng bước:
   /scaffold-entity → /scaffold-dto → /scaffold-cqrs-command → ... → /run-migration

Thêm RabbitMQ consumer:
2. /scaffold-integration-event BatteryAnomalyDetectedEvent
3. /scaffold-consumer TicketService BatteryAnomalyDetectedEvent

Viết unit tests:
4. /scaffold-unit-tests BatteryService Battery
```
