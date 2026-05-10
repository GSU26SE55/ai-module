# Hướng dẫn sử dụng Claude Code — Team GSU26SE55

## Yêu cầu cài đặt (tất cả mọi người)

| Công cụ | Phiên bản |
|---------|-----------|
| [Claude Code](https://claude.ai/code) | Mới nhất — bắt buộc |
| Node.js | 18+ |
| Git | 2.30+ |
| Python | 3.x (cho pre-commit) |
| Tài khoản GitHub | Đã được Leader invite vào org `GSU26SE55` |

---

## SETUP — Làm 1 lần khi join project

### Bước 1 — Lấy Jira API Token

1. Đăng nhập Atlassian → https://id.atlassian.com/manage-profile/security/api-tokens
2. Nhấn **Create API token** → đặt tên (VD: `claude-code`) → **Copy token**

Giữ bí mật — không share, không commit.

---

### Bước 2 — Clone repo theo role chính

| Thành viên | Role chính | Role phụ | Clone repo chính |
|------------|------------|----------|-----------------|
| Nguyễn Phúc Duy | BE | FE, AI | `git clone https://github.com/GSU26SE55/backend.git` |
| Bùi Phước Thắng | BE | FE, AI | `git clone https://github.com/GSU26SE55/backend.git` |
| Mai Hồng Thái | BE | FE, AI | `git clone https://github.com/GSU26SE55/backend.git` |
| Trần Minh Trí | FE (Leader) | BE, AI | clone tất cả (xem mục Leader) |
| Nguyễn Nhật Minh | FE | BE, AI | `git clone https://github.com/GSU26SE55/frontend.git` |

> Nếu được assign task role phụ: clone thêm repo đó, tạo `CLAUDE.local.md` với đúng role phụ đang làm.

---

### Bước 3 — Tạo CLAUDE.local.md (trong folder repo vừa clone)

Tạo file `.claude/CLAUDE.local.md` (không commit — đã có trong `.gitignore`):

**BE Dev (Duy / Thắng / Thái) — làm task BE:**
```
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
Role chính: BE
Role phụ: FE, AI
```

**BE Dev — khi làm task FE phụ (clone frontend repo):**
```
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
Role chính: BE
Role phụ: FE, AI
Đang làm: FE (role phụ)
```

**FE Dev (Minh) — làm task FE:**
```
Tên: Nguyễn Nhật Minh
MSSV: SE170310
Role chính: FE
Role phụ: BE, AI
```

**Khi làm task AI (mọi thành viên — clone ai-module):**
```
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
Role chính: [Role chính của bạn]
Role phụ: FE, AI   (hoặc BE, AI)
Đang làm: AI (role phụ)
```

---

### Bước 4 — Cấu hình Jira MCP

> **Tại sao không để trong `.mcp.json`?**
> `.mcp.json` được commit lên Git (shared với team) → không được chứa credentials.
> `.claude/settings.local.json` đã có trong `.gitignore` → an toàn để lưu token.

Tạo (hoặc mở) file `.claude/settings.local.json` trong folder repo của bạn:

```json
{
  "mcpServers": {
    "jira": {
      "command": "npx",
      "args": ["-y", "@rui.branco/jira-mcp"],
      "env": {
        "JIRA_BASE_URL": "https://fpt-team-d7rg7yak.atlassian.net",
        "JIRA_EMAIL": "<email fpt của bạn>",
        "JIRA_API_TOKEN": "<token Jira từ Bước 1>"
      }
    }
  }
}
```

Claude Code merge `settings.local.json` với `.mcp.json` khi khởi động — bạn sẽ thấy đủ 2 MCP: `context7`, `jira`.

---

### Bước 5 — Cài pre-commit hooks

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push
```

Chạy trong folder repo. Làm **1 lần** — hook tự chạy mỗi lần commit / push.

> `--hook-type pre-push` là bắt buộc — thiếu dòng này thì hook chặn push thẳng lên main sẽ không hoạt động.

---

### Bước 6 — Mở Claude Code và verify

> **Quan trọng:** Claude Code phải được mở từ **bên trong folder repo** — không phải từ Desktop hay thư mục tuỳ ý. Claude Code đọc `.claude/` trong thư mục hiện tại để load đúng rules, hooks và skills của dự án. Mở sai thư mục → không có lệnh `/kltn-*`.

```bash
# BE Dev
cd ~/Documents/GSU26SE55/backend
claude

# FE Dev
cd ~/Documents/GSU26SE55/frontend
claude

# Đang làm task role phụ (ví dụ BE làm task FE)
cd ~/Documents/GSU26SE55/frontend   # cd vào repo của role đang làm
claude
```

Sau khi Claude Code mở, gõ `/mcp` — phải thấy `jira: connected` (và `context7` nếu có).

Nếu `jira: disconnected` → kiểm tra lại token ở Bước 4.

Gõ `/` để xem danh sách lệnh Claude Code. Xem bảng **Danh sách lệnh** ở cuối trang để biết các lệnh `/kltn-*` của dự án.

---

## LEADER — Setup riêng (Trần Minh Trí)

### Bước 2L — Clone tất cả repo

```bash
mkdir GSU26SE55 && cd GSU26SE55
git clone https://github.com/GSU26SE55/workflow-ai.git
git clone https://github.com/GSU26SE55/backend.git
git clone https://github.com/GSU26SE55/frontend.git
git clone https://github.com/GSU26SE55/mobile.git
git clone https://github.com/GSU26SE55/ai-module.git
```

Thêm remote `workflow-ai` cho các sub-repo (để sync config):

```bash
for repo in backend frontend mobile ai-module; do
  cd $repo
  git remote add workflow-ai https://github.com/GSU26SE55/workflow-ai.git
  cd ..
done
```

### Bước 3L — CLAUDE.local.md trong workflow-ai

```
Tên: Trần Minh Trí
MSSV: SE183109
Role chính: FE (Leader)
Role phụ: BE, AI
```

### Bước 4L — Cấu hình Jira MCP ở user scope

Leader làm việc trên nhiều repo → cài Jira MCP ở **user scope** để dùng được ở mọi nơi mà không cần cấu hình lại từng repo.

Mở `~/.claude/settings.json` (file global của Claude Code), thêm block `mcpServers`:

```json
{
  "mcpServers": {
    "jira": {
      "command": "npx",
      "args": ["-y", "@rui.branco/jira-mcp"],
      "env": {
        "JIRA_BASE_URL": "https://fpt-team-d7rg7yak.atlassian.net",
        "JIRA_EMAIL": "<email của bạn>",
        "JIRA_API_TOKEN": "<token Jira từ Bước 1>"
      }
    }
  }
}
```

> `~/.claude/settings.json` nằm ngoài mọi Git repo — không có rủi ro commit nhầm token.

### Bước 5L — Pre-commit cho tất cả sub-repos

```bash
pip install pre-commit
for repo in backend frontend mobile ai-module; do
  cd $repo && pre-commit install && pre-commit install --hook-type commit-msg && pre-commit install --hook-type pre-push && cd ..
done
```

### Bước 6L — Mở Claude Code từ workflow-ai

```bash
cd workflow-ai
claude
```

---

## Chạy toàn bộ hệ thống local (Docker Compose)

> Yêu cầu: Docker Desktop đang chạy. Đã clone tất cả sub-repo về cùng cấp với `workflow-ai`.

```bash
# 1. Tạo file .env
cd workflow-ai
cp .env.example .env
# (mặc định đủ dùng cho local, không cần sửa)

# 2. Khởi động
docker compose up -d

# 3. Kiểm tra
docker compose ps

# 4. Xem log
docker compose logs -f backend
docker compose logs -f ai-module

# 5. Dừng
docker compose down
```

**Services và port:**

| Service | Port | URL |
|---------|------|-----|
| Backend (ASP.NET Core) | 5000 | http://localhost:5000 |
| AI Module (FastAPI) | 8001 | http://localhost:8001/docs |
| Frontend (React build) | 3000 | http://localhost:3000 |
| PostgreSQL / TimescaleDB | 5432 | — |
| Redis | 6379 | — |
| RabbitMQ Management | 15672 | http://localhost:15672 |

> **Dev thường ngày:** chạy `npm run dev` / `dotnet run` trực tiếp — Docker dùng để test integration.

---

## Luồng làm việc hàng ngày

```
git pull                    ← lấy code mới nhất (gồm cả .claude/ đã sync)

/kltn-task KAN-XX           ← Claude đọc Jira, phân tích codebase, gợi ý approach
                            ← Claude viết plan.md → logs/KAN-XX/plan.md
                            ← Bạn review plan → gõ "ok" / "approve" để xác nhận
                            ⚠️  Claude KHÔNG code trước khi có xác nhận

code...

/kltn-reviewcode            ← Claude review diff → PASS hoặc FAIL
                            ← Sửa nếu FAIL → /kltn-reviewcode lại

/kltn-test KAN-XX           ← Claude chạy test → PASS hoặc FAIL
                            ← Sửa nếu FAIL → /kltn-test lại

/kltn-ship KAN-XX           ← Claude tạo PR + update Jira → IN REVIEW

/kltn-reviewpr KAN-XX       ← Review PR của đồng đội → APPROVE hoặc REQUEST CHANGES

Merge trên GitHub UI        ← sau khi có ≥ 1 approve
```

---

## Danh sách lệnh

### Dev (tất cả role)

| Lệnh | Khi nào dùng |
|------|-------------|
| `/kltn-task KAN-XX` | Bắt đầu ticket — đọc Jira, phân tích, lên plan |
| `/kltn-reviewcode` | Review code trước khi test |
| `/kltn-test KAN-XX` | Test sau khi reviewcode PASS |
| `/kltn-ship KAN-XX` | Tạo PR + update Jira |
| `/kltn-reviewpr KAN-XX` | Review PR của đồng đội |

### Scaffold BE (tạo boilerplate nhanh)

| Lệnh | Output |
|------|--------|
| `/scaffold-crud {Service} {Entity}` | 14 files + migration |
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
| `/kltn-sprint` | Lên kế hoạch sprint, phân công task từ Jira |
| `/kltn-team` | Báo cáo tiến độ toàn team |
| `/kltn-member [tên]` | Check tiến độ từng người |

### MCP tools

```
# Context7 — tra docs
dùng context7 tìm cách dùng IMediator trong MediatR .NET
dùng context7 tìm cách dùng useMutation trong TanStack Query v5
```

---

## Definition of Done

Ticket chỉ được coi là **Done** khi đủ cả 3:

1. `/kltn-reviewcode` → **PASS**
2. `/kltn-test` → **PASS**
3. PR được ≥ 1 người approve và **merged vào main**

---

## Quy tắc bắt buộc

- **Không merge PR của chính mình** — cần ít nhất 1 người approve
- **Không push thẳng lên main** — luôn qua PR
- **1 ticket = 1 branch** — `feature/KAN-XX-ten-ngan`
- **Commit format:** `feat(KAN-XX): mô tả` / `fix` / `refactor` / `test`
- **Không commit** `CLAUDE.local.md` — đã có trong `.gitignore`
- **Không tự thêm package** ngoài stack trong `rules/tech/` — hỏi Leader trước

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
git add .claude/
git commit -m "chore: mô tả thay đổi"
git push org-workflow main --no-verify   # trigger GitHub Actions (--no-verify bypass pre-push hook)
```

Theo dõi Actions tại: https://github.com/GSU26SE55/workflow-ai/actions

---

## Cần hỗ trợ

Liên hệ Leader: **Trần Minh Trí (SE183109)**
