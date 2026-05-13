# Setup — GSU26SE55 (làm 1 lần khi join project)

## Yêu cầu cài đặt

| Công cụ | Phiên bản |
|---------|-----------|
| [Claude Code](https://claude.ai/code) | Mới nhất — bắt buộc |
| [GitHub CLI (`gh`)](https://cli.github.com/) | 2.40+ — bắt buộc |
| [RTK](https://github.com/rtk-ai/rtk) | Mới nhất — bắt buộc |
| Node.js | 18+ |
| Git | 2.30+ |
| Python | 3.x (cho pre-commit) |
| Tài khoản GitHub | Đã được Leader invite vào org `GSU26SE55` |

---

## MEMBER — Setup (Duy / Thắng / Thái / Minh)

### Bước 1 — Đăng nhập GitHub CLI

```bash
gh auth login
```

Chọn: **GitHub.com** → **HTTPS** → **Login with a web browser**

Kiểm tra:
```bash
gh auth status
# ✓ Logged in to github.com account <username>
```

---

### Bước 2 — Clone repo theo role chính

| Thành viên | Clone lệnh |
|------------|-----------|
| Nguyễn Phúc Duy (BE) | `git clone https://github.com/GSU26SE55/backend.git` |
| Bùi Phước Thắng (BE) | `git clone https://github.com/GSU26SE55/backend.git` |
| Mai Hồng Thái (BE) | `git clone https://github.com/GSU26SE55/backend.git` |
| Nguyễn Nhật Minh (FE) | `git clone https://github.com/GSU26SE55/frontend.git` |

> Nếu được assign task role phụ → clone thêm repo đó và tạo `CLAUDE.local.md` với role phụ đang làm.

---

### Bước 3 — Tạo CLAUDE.local.md

Tạo file `.claude/CLAUDE.local.md` **bên trong folder repo vừa clone** (không commit):

**BE Dev (Duy / Thắng / Thái):**
```
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
Role chính: BE
Role phụ: FE, AI
```

**FE Dev (Minh):**
```
Tên: Nguyễn Nhật Minh
MSSV: SE170310
Role chính: FE
Role phụ: BE, AI
```

**Khi làm task role phụ (ví dụ BE làm task FE):**
```
Tên: [Tên của bạn]
MSSV: [MSSV của bạn]
Role chính: BE
Role phụ: FE, AI
Đang làm: FE (role phụ)
```

---

### Bước 4 — Cài pre-commit hooks

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push
```

Chạy trong folder repo. Làm **1 lần** — hook tự chạy mỗi lần commit / push.

---

### Bước 5 — Cài RTK (token saver cho Claude Code)

RTK nén output của các lệnh (build, test, git, gh...) trước khi gửi vào Claude — giảm 60–90% token tiêu thụ. Đã được cấu hình sẵn trong `workflow-ai/CLAUDE.md`; Claude Code tự dùng `rtk` prefix khi chạy commands, không cần làm thêm gì.

**macOS:**
```bash
brew install rtk
```

**Windows (WSL — khuyến nghị):**
```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
```
> Chạy lệnh này bên trong terminal WSL (Ubuntu). Nếu chưa có WSL: `wsl --install` trong PowerShell (Admin) rồi restart.

**Windows (native — không dùng WSL):**
1. Tải file `rtk-x86_64-pc-windows-msvc.zip` tại [github.com/rtk-ai/rtk/releases](https://github.com/rtk-ai/rtk/releases)
2. Giải nén → copy `rtk.exe` vào một thư mục trong PATH (ví dụ `C:\Tools\`)
3. Thêm thư mục đó vào System PATH nếu chưa có

Kiểm tra:
```bash
rtk --version   # in ra phiên bản
```

---

### Bước 6 — Mở Claude Code và verify

> Claude Code **phải mở từ bên trong folder repo** — mở sai thư mục → không có lệnh `/kltn-*`.

```bash
# BE Dev
cd ~/Documents/GSU26SE55/backend && claude

# FE Dev
cd ~/Documents/GSU26SE55/frontend && claude

# Làm task role phụ → cd vào repo của role đó
cd ~/Documents/GSU26SE55/ai-module && claude
```

Kiểm tra sau khi mở:
```bash
gh auth status                                      # ✓ Logged in
gh issue list --repo GSU26SE55/backend --limit 5    # thấy issues → OK
rtk --version                                       # ✓ RTK installed
```

Gõ `/kltn-guide` để xem hướng dẫn sử dụng.

---

## LEADER — Setup riêng (Trần Minh Trí — SE183109)

### Bước 1L — Đăng nhập GitHub CLI với scope project

```bash
gh auth login
gh auth refresh --hostname github.com --scopes project
```

---

### Bước 2L — Clone tất cả repo

```bash
mkdir -p ~/Documents/GSU26SE55 && cd ~/Documents/GSU26SE55
git clone https://github.com/GSU26SE55/workflow-ai.git
git clone https://github.com/GSU26SE55/backend.git
git clone https://github.com/GSU26SE55/frontend.git
git clone https://github.com/GSU26SE55/mobile.git
git clone https://github.com/GSU26SE55/ai-module.git
```

---

### Bước 3L — Tạo CLAUDE.local.md trong workflow-ai

```
Tên: Trần Minh Trí
MSSV: SE183109
Role chính: FE (Leader)
Role phụ: BE, AI
```

---

### Bước 4L — Sync labels + milestones xuống tất cả sub-repos (1 lần)

```bash
cd ~/Documents/GSU26SE55/workflow-ai
bash .github/setup-github.sh
```

Script tự động tạo đủ labels (17 labels) và milestones (8 sprints) trong tất cả 4 sub-repos.

---

### Bước 5L — Thêm secret SYNC_TOKEN vào sub-repos

Vào Settings của từng repo → Secrets and variables → Actions → **New repository secret**:
- Name: `SYNC_TOKEN`
- Value: (cùng token với `workflow-ai`, cần scope `repo` + `project`)

Lặp lại cho: `backend` · `frontend` · `mobile` · `ai-module`

---

### Bước 6L — Điền GitHub usernames

Mở 2 file và điền username thực của từng người:
- `.claude/commands/kltn-team.md`
- `.claude/commands/kltn-member.md`

```bash
cd workflow-ai
git checkout -b chore/add-github-usernames
git add .claude/commands/kltn-team.md .claude/commands/kltn-member.md
git commit -m "chore: điền GitHub usernames cho team"
git push origin chore/add-github-usernames
# Mở PR → merge
```

---

### Bước 7L — Cài pre-commit cho tất cả sub-repos

```bash
pip install pre-commit
for repo in backend frontend mobile ai-module; do
  cd ~/Documents/GSU26SE55/$repo
  pre-commit install
  pre-commit install --hook-type commit-msg
  pre-commit install --hook-type pre-push
done
```

---

### Bước 8L — Cài RTK

Tương tự Member — xem **Bước 5** ở trên (macOS / Windows / WSL). Đã cấu hình sẵn, không cần làm thêm gì.

---

### Bước 9L — Mở Claude Code từ workflow-ai

```bash
cd ~/Documents/GSU26SE55/workflow-ai
claude
```

Gõ `/kltn-guide` để xem hướng dẫn sử dụng.
