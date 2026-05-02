# Hướng dẫn sử dụng Claude Code — Team GSU26SE55

## Yêu cầu cài đặt

- [Claude Code CLI](https://claude.ai/code) — bắt buộc
- Node.js 18+
- Git

---

## LEADER — Setup (Trần Minh Trí)

> Leader làm việc từ folder `Search` (workflow-ai), không phải role repo.

### Bước 1 — Mở Claude Code từ đúng folder

```bash
cd C:\Users\ttei8\Desktop\Project\Search
claude
```

### Bước 2 — Tạo `.claude/CLAUDE.local.md`

```
Role: Leader
Dev Role: FE
Tên: Trần Minh Trí
MSSV: SE183109
```

### Bước 3 — Setup Jira MCP (user scope — dùng được ở mọi repo)

Leader làm việc trên nhiều repo (workflow-ai + các sub-repo), nên cài MCP ở **user scope**.

**Lấy Jira API Token:**
1. Vào https://id.atlassian.com/manage-profile/security/api-tokens
2. Nhấn **Create API token** → đặt tên → Copy token

```bash
# 1. Lưu credentials (chỉ chạy 1 lần)
npx -y @rui.branco/jira-mcp setup "<email fpt>" "<API token>" "https://fpt-team-d7rg7yak.atlassian.net"

# 2. Đăng ký MCP ở user scope (có hiệu lực trong mọi folder)
claude mcp add --scope user jira npx -- -y @rui.branco/jira-mcp
```

> **Tại sao user scope?** Project scope (mặc định) chỉ hoạt động trong folder `workflow-ai`. User scope cho phép dùng Jira MCP trong `frontend`, `backend`, v.v. mà không cần cấu hình lại.

### Bước 4 — Verify

Mở Claude Code → gõ `/mcp` → thấy `jira: connected` là xong.

---

## MEMBER — Setup (FE / BE / Mobile / AI Dev)

> Member clone role repo về máy, làm việc từ folder role repo đó. **Không dùng folder `Search`.**

### Bước 1 — Clone role repo và mở Claude Code

Clone đúng repo theo role của bạn:

| Role | Repo |
|------|------|
| FE | `GSU26SE55/frontend` |
| BE | `GSU26SE55/backend` |
| Mobile | `GSU26SE55/mobile` |
| AI | `GSU26SE55/ai-module` |

```bash
# Ví dụ FE dev:
cd C:\Users\<tên máy>\Desktop\Project\GSU26SE55\frontend
claude
```

> Phải mở Claude Code từ folder role repo của bạn — không mở folder khác.

### Bước 2 — Tạo `.claude/CLAUDE.local.md` (không commit)

Tạo file `.claude/CLAUDE.local.md` ngay trong folder role repo:

**FE Dev:**
```
Role: FE
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

**BE Dev:**
```
Role: BE
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

**Mobile Dev:**
```
Role: Mobile
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

**AI Dev:**
```
Role: AI
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

### Bước 3 — Setup Jira MCP trong `settings.local.json`

**Lấy Jira API Token:**
1. Vào https://id.atlassian.com/manage-profile/security/api-tokens
2. Nhấn **Create API token** → đặt tên → Copy token

Mở `.claude/settings.local.json` trong folder role repo, thêm block `mcpServers` (giữ nguyên phần `permissions` nếu đã có):

```json
{
  "mcpServers": {
    "jira": {
      "command": "npx",
      "args": ["-y", "@rui.branco/jira-mcp"],
      "env": {
        "JIRA_BASE_URL": "https://fpt-team-d7rg7yak.atlassian.net",
        "JIRA_EMAIL": "<email fpt của bạn>",
        "JIRA_API_TOKEN": "<token Jira của bạn>"
      }
    }
  }
}
```

> `settings.local.json` đã có trong `.gitignore` — token không bị commit lên Git.

### Bước 4 — Verify

Mở Claude Code → gõ `/mcp` → thấy `jira: connected` là xong.

---

## Sử dụng hàng ngày

### Mở Claude Code

**Leader:**
```bash
cd C:\Users\ttei8\Desktop\Project\Search
claude
```

**Member (ví dụ FE):**
```bash
cd C:\Users\<tên máy>\Desktop\Project\GSU26SE55\frontend
claude
```

### Xem toàn bộ commands

```
/kltn
```

---

### Các lệnh dev dùng hàng ngày

| Lệnh | Khi nào dùng |
|------|-------------|
| `/kltn-task KAN-XX` | Bắt đầu làm 1 ticket — đọc ticket, lập plan, code |
| `/kltn-reviewcode` | Review code trước khi test |
| `/kltn-test KAN-XX` | Kiểm thử sau khi reviewcode PASS |
| `/kltn-ship KAN-XX` | Tạo PR + cập nhật Jira |
| `/kltn-reviewpr KAN-XX` | Review PR của đồng đội, approve hoặc request changes |

---

### Luồng chuẩn mỗi ticket

```
1. /kltn-task KAN-XX   → Claude đọc ticket, phân tích context
2. Plan + viết file    → Claude viết logs/KAN-XX/plan.md
3. Bạn review plan     → Gõ "ok" / "approve" / "tiến hành" để xác nhận
                         ⚠️ Claude KHÔNG code trước khi có xác nhận này
4. Code...
5. /kltn-reviewcode    → Claude review diff, báo PASS hoặc FAIL
6. Sửa nếu FAIL        → /kltn-reviewcode lại
7. /kltn-test KAN-XX   → Claude chạy test cases, báo PASS hoặc FAIL
8. Sửa nếu FAIL        → /kltn-test lại
9. /kltn-ship KAN-XX   → Claude tạo PR, update Jira sang IN REVIEW
10. Đồng đội /kltn-reviewpr → APPROVE hoặc REQUEST CHANGES
11. Sau approve        → merge trên GitHub
```

---

### Estimate size khi lập plan

| Size | Thời gian | Hành động sau khi approve |
|------|-----------|--------------------------|
| Small | < 2 giờ | Code luôn |
| Medium | 2–4 giờ | Code luôn |
| Large | > 4 giờ | Yêu cầu apprvoed trước khi code |

> **Mọi ticket đều phải có `logs/KAN-XX/plan.md` được approve trước khi code. Không có ngoại lệ.**

---

### Definition of Done

Ticket chỉ được coi là **Done** khi đủ cả 3:
1. `/kltn-reviewcode` → **PASS**
2. `/kltn-test` → **PASS**
3. PR được ≥ 1 người approve và **merged vào main**

---

## Lệnh của Leader

| Lệnh | Tác dụng |
|------|---------|
| `/kltn-sprint` | Lên kế hoạch sprint, phân công task từ Jira |
| `/kltn-team` | Báo cáo tiến độ toàn team + QA research |
| `/kltn-member [tên]` | Check tiến độ từng người |

---

## Quy tắc bắt buộc

- **Không merge PR của chính mình** — cần ít nhất 1 người approve
- **Không push thẳng lên main** — luôn qua PR
- **1 ticket = 1 branch** — `feature/KAN-XX-ten-ngan`
- **Không commit** `.env`, `.claude/.env`, `CLAUDE.local.md` — đã có trong `.gitignore`
- **Commit format:** `feat(KAN-XX): mô tả` / `fix` / `refactor` / `test`
- Chỉ dùng tech stack trong `.claude/rules/tech/` theo role — không tự thêm package lạ

---

## Cập nhật Skills / Config

> Mọi thay đổi `.claude/` phải đi qua `workflow-ai` → Leader review → mới sync xuống.
> **Không sửa trực tiếp trong role repo** — sẽ bị ghi đè khi Leader sync.

```bash
# 1. Clone workflow-ai (làm 1 lần)
git clone https://github.com/GSU26SE55/workflow-ai.git && cd workflow-ai

# 2. Tạo branch
git checkout -b fix/ten-thay-doi

# 3. Sửa file trong .claude/

# 4. Commit và push
git add .claude/
git commit -m "fix: mô tả thay đổi"
git push origin fix/ten-thay-doi

# 5. Mở PR trên GitHub → assign Leader review
```

Sau khi Leader merge → GitHub Actions tự động sync xuống 4 repo con. Member chỉ cần `git pull` để nhận bản mới.

---

## Bảo vệ code — Pre-commit & GitHub Actions

### Cài đặt pre-commit (mỗi thành viên làm 1 lần sau khi clone)

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

### Những gì bị kiểm tra tự động

| Hook | Kiểm tra gì | Role |
|------|-------------|------|
| `no-commit-to-branch` | Chặn commit thẳng vào `main` | Tất cả |
| `conventional-pre-commit` | Format commit message | Tất cả |
| `trailing-whitespace` | Khoảng trắng thừa | Tất cả |
| `eslint` + `tsc` | Lint + type check | FE / Mobile |
| `dotnet format` | Code style C# | BE |
| `ruff` + `ruff-format` | Lint + format Python | AI |

### Commit message bắt buộc

```
feat(KAN-XX): mô tả ngắn gọn
fix(KAN-XX): mô tả ngắn gọn
refactor(KAN-XX): mô tả ngắn gọn
test(KAN-XX): mô tả ngắn gọn
```

---

## Quản lý config (Leader only)

> **Không cần clone local các role repo.** GitHub Actions tự động sync khi Leader push.

### Auto-sync (khuyến nghị)

Mỗi khi push thay đổi trong `.claude/` hoặc `templates/` lên `workflow-ai`, GitHub Actions sẽ tự động sync xuống 4 repo con.

```
Sửa .claude/  →  git push  →  GitHub Actions sync → member git pull
```

Theo dõi kết quả tại: https://github.com/GSU26SE55/workflow-ai/actions

### Manual trigger

Nếu cần sync ngay mà không có thay đổi file:
1. Vào https://github.com/GSU26SE55/workflow-ai/actions
2. Chọn **"Sync config to sub-repos"**
3. Nhấn **Run workflow**

---

## Cần hỗ trợ

Liên hệ Leader: **Trần Minh Trí (SE183109)**
