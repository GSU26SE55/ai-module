# Hướng dẫn sử dụng Claude Code — Team GSU26SE55

## Yêu cầu cài đặt

- [Claude Code CLI](https://claude.ai/code) — bắt buộc
- Node.js 18+
- Git

---

## Lần đầu setup (làm 1 lần duy nhất)

### Bước 1 — Clone repo và mở đúng folder

```bash
cd C:\Users\<tên máy>\Desktop\Project\Search
claude
```

> Phải mở Claude Code từ folder `Search` — không mở folder khác.

---

### Bước 2 — Tạo file CLAUDE.local.md (không commit)

Tạo file `.claude/CLAUDE.local.md` với nội dung theo role của bạn:

**Nếu là BE Dev:**
```
Role: BE
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

**Nếu là FE Dev:**
```
Role: FE
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

**Nếu là Leader (kiêm dev):**
```
Role: Leader
Dev Role: FE   ← hoặc BE / AI tùy vị trí thực tế
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

**Nếu là AI Dev:**
```
Role: AI
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
```

---

### Bước 3 — Tạo file .env (không commit)

Tạo file `.env` ở root folder `Search`:

```
JIRA_BASE_URL=https://fpt-team-d7rg7yak.atlassian.net
JIRA_EMAIL=<email fpt của bạn>
JIRA_API_TOKEN=<token Jira của bạn>
```

**Lấy Jira API Token:**
1. Vào https://id.atlassian.com/manage-profile/security/api-tokens
2. Nhấn **Create API token**
3. Đặt tên → Copy token

---

### Bước 4 — Setup Jira MCP

Chạy lệnh này trong terminal (thay thông tin của bạn):

```bash
npx -y @rui.branco/jira-mcp setup "<email fpt>" "<API token>" "https://fpt-team-d7rg7yak.atlassian.net"
```

Sau đó đăng ký MCP server:

```bash
claude mcp add --transport stdio jira -- npx -y @rui.branco/jira-mcp
```

---

### Bước 5 — Verify

Mở Claude Code → gõ `/mcp` → thấy `jira: connected` là xong.

---

## Sử dụng hàng ngày

### Mở Claude Code

```bash
cd C:\Users\<tên máy>\Desktop\Project\Search
claude
```

### Xem toàn bộ commands

```
/kltn
```

Gõ lệnh này bất kỳ lúc nào để xem danh sách đầy đủ.

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
                           (Scope, Files, Approach, Edge cases, Estimate)
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
| Large | > 4 giờ | **Hỏi Leader trước khi code** |

> **Mọi ticket đều phải có `logs/KAN-XX/plan.md` được approve trước khi code. Không có ngoại lệ.**

---

### Definition of Done

Ticket chỉ được coi là **Done** khi đủ cả 3:
1. `/kltn-reviewcode` → **PASS**
2. `/kltn-test` → **PASS**
3. PR được ≥ 1 người approve và **merged vào main**

---

## Lệnh của Leader (Trần Minh Trí — SE183109)

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
- **Không commit** `.env` và `CLAUDE.local.md` — đã có trong `.gitignore`
- **Commit format:** `feat(KAN-XX): mô tả` / `fix` / `refactor` / `test`
- Chỉ dùng tech stack trong `.claude/rules/tech-defaults.md` — không tự thêm package lạ

---

## Cần hỗ trợ

Liên hệ Leader: **Trần Minh Trí (SE183109)**

---

## Cập nhật Skills / Config — Dành cho tất cả thành viên

> Đây là cách duy nhất để đề xuất thay đổi skills, rules, hoặc bất kỳ file nào trong `.claude/`.
> **Không sửa trực tiếp trong role repo** (backend / frontend / mobile / ai-module) — sẽ bị ghi đè khi Leader sync.

---

### Tại sao phải làm theo cách này?

```
workflow-ai (GitHub)  ←  source of truth duy nhất cho .claude/
        ↓
  push-config.sh
        ↓
backend / frontend / mobile / ai-module  ←  chỉ nhận, không sửa
```

Mọi thay đổi phải đi qua `workflow-ai` → Leader review → mới sync xuống tất cả.

---

### Bước 1 — Clone `workflow-ai` về máy (làm 1 lần)

```bash
git clone https://github.com/GSU26SE55/workflow-ai.git
cd workflow-ai
```

> Nếu đã clone rồi, pull bản mới nhất trước:
> ```bash
> git pull origin main
> ```

---

### Bước 2 — Tạo branch mới

```bash
git checkout -b fix/ten-thay-doi
```

Ví dụ: `fix/update-task-skill-be`, `fix/them-rule-commit`, `fix/sua-checklist-ship`

---

### Bước 3 — Sửa file trong `.claude/`

Các file thường cần sửa:

| File | Khi nào sửa |
|------|-------------|
| `.claude/skills/dev/be/task.md` | Checklist task của BE cần cập nhật |
| `.claude/skills/dev/fe/task.md` | Checklist task của FE cần cập nhật |
| `.claude/rules/workflow.md` | Quy trình làm việc thay đổi |
| `.claude/rules/tech-defaults.md` | Thêm/bỏ package, công nghệ |

---

### Bước 4 — Commit và push

```bash
git add .claude/
git commit -m "fix: mô tả thay đổi"
git push origin fix/ten-thay-doi
```

---

### Bước 5 — Mở Pull Request

1. Vào `https://github.com/GSU26SE55/workflow-ai`
2. GitHub sẽ hiện banner **"Compare & pull request"** → bấm vào
3. Điền mô tả ngắn gọn thay đổi là gì và tại sao
4. Assign **Leader (Trần Minh Trí)** để review

---

### Sau khi Leader merge

Leader sẽ chạy `push-config.sh` để sync xuống tất cả role repos.

Bạn chỉ cần `git pull` ở role repo của mình để nhận bản mới:

```bash
git pull origin main
```

---

### Lưu ý quan trọng

- **Không push thẳng vào `main`** của `workflow-ai` — branch protection đã bật
- **Không sửa file ngoài `.claude/`** trong repo này
- **1 PR = 1 thay đổi cụ thể** — không gộp nhiều thứ không liên quan vào 1 PR
- Nếu không chắc nên sửa gì → nhắn Leader trước, đừng tự sửa

---

## Quản lý config (Leader only)

### Cập nhật .claude/ config xuống tất cả role repos

Mỗi khi Leader sửa bất kỳ file nào trong `workflow-ai` (Search), chạy **1 lệnh** để sync xuống `backend` / `frontend` / `mobile` / `ai-module`:

```bash
cd C:\Users\ttei8\Desktop\Project\Search
git push-config
```

Hoặc:

```bash
bash push-config.sh
```

Lệnh này tự động làm 3 việc:
1. Push `workflow-ai` lên GitHub org
2. Cập nhật branch `subtree/claude-config`
3. Sync `.claude/` xuống 4 role repos và push

Sau khi sync xong, member chỉ cần `git pull` để nhận config mới.

### Yêu cầu

Các folder role repos phải tồn tại trên máy Leader:

```
C:\Users\ttei8\Desktop\Project\GSU26SE55\
├── backend\
├── frontend\
├── mobile\
└── ai-module\
```

---

## Cấu trúc thư mục tham khảo

```
.claude/
├── CLAUDE.md              ← bộ não dự án (đọc để hiểu context)
├── rules/                 ← quy tắc coding, design, tech stack
├── commands/              ← slash commands (/kltn, /kltn-task, ...)
├── skills/dev/be|fe|ai/   ← chi tiết checklist theo role
├── agents/                ← researcher + reviewer + tester
└── docs/                  ← file hướng dẫn này
```
