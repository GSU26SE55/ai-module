Tạo GitHub Issue mới (skeleton) vào sub-repo tương ứng với role. Context chi tiết sẽ được post sau khi chạy `/kltn-plan`.

---

## ⚠️ NGUYÊN TẮC BẮT BUỘC

> **Dừng và chờ user xác nhận trước khi gọi `gh issue create`.** Không tạo issue tự động.

---

**Bước 0 — Lấy context người dùng**

```bash
# Đọc role từ CLAUDE.local.md
cat .claude/CLAUDE.local.md 2>/dev/null || cat CLAUDE.local.md 2>/dev/null

# Lấy GitHub username đang login
gh api user --jq '.login'
```

Mapping role → repo:
| Role | Repo |
|------|------|
| BE | `GSU26SE55/backend` |
| FE | `GSU26SE55/frontend` |
| Mobile | `GSU26SE55/mobile` |
| AI | `GSU26SE55/ai-module` |

Ghi nhớ `$MY_ROLE`, `$MY_LOGIN`, `$REPO`.

Nếu thiếu Role chính trong CLAUDE.local.md → dừng và yêu cầu tạo file trước.
Nếu có role phụ → hỏi issue này thuộc role nào để chọn đúng repo.

---

**Bước 1 — Lấy milestone đang mở**

```bash
gh api repos/GSU26SE55/$REPO/milestones --jq '.[] | select(.state=="open") | "\(.title) (due: \(.due_on // "no date"))"'
```

Ghi nhớ `$SPRINT_NAME` (milestone có due date sớm nhất).

---

**Bước 2 — Thu thập thông tin từ user**

Hỏi một lần:

```
Cần biết để tạo issue:

1. Tiêu đề: (ví dụ: "Add Battery CRUD API")
2. Mô tả ngắn: task này làm gì? (1–2 câu, có thể để trống nếu chưa rõ)
3. Type: feat / fix / refactor / test / docs / chore  [default: feat]
4. Priority: P1 Critical (4h) / P2 High (24h) / P3 Standard (72h)  [default: P3]
5. Assign cho ai? GitHub username  [default: @$MY_LOGIN]
6. Sprint:  [default: $SPRINT_NAME]
```

> Không hỏi Acceptance Criteria hay technical notes — những thứ đó xác định khi `/kltn-plan`.

---

**Bước 3 — Kiểm tra trùng lặp**

```bash
gh issue list \
  --repo "GSU26SE55/$REPO" \
  --state open \
  --search "$TITLE" \
  --json number,title \
  --limit 5
```

Nếu có issue tương tự → cho user xem và xác nhận có muốn tạo mới không.

---

**Bước 4 — Xác nhận**

Hiện summary và chờ user gõ "ok":

```
📋 Xác nhận tạo issue:

  Repo:    GSU26SE55/$REPO
  Title:   [$ROLE] $TITLE
  Sprint:  $SPRINT_NAME
  Assign:  @$ASSIGNEE
  Labels:  status: init  |  role: $ROLE  |  type: $TYPE  |  priority: $PRIORITY

  Mô tả: $DESCRIPTION (hoặc "(chưa có — sẽ cập nhật sau khi plan)")

Gõ "ok" để tạo.
```

> **DỪNG — chờ user xác nhận trước khi chạy `gh issue create`.**

---

**Bước 5 — Tạo issue**

```bash
gh issue create \
  --repo "GSU26SE55/$REPO" \
  --title "[$ROLE] $TITLE" \
  --body "$(cat <<'EOF'
## Mô tả
$DESCRIPTION

---
> Context chi tiết (plan, approach, AC) sẽ được cập nhật sau khi chạy `/kltn-plan $ISSUE_NUMBER`.
EOF
)" \
  --label "status: init,role: $ROLE,type: $TYPE,priority: $PRIORITY" \
  --milestone "$SPRINT_NAME" \
  --assignee "$ASSIGNEE"
```

> **4 nhóm label bắt buộc:** `status: init` · `role: *` · `type: *` · `priority: *`

---

**Bước 6 — Xuất kết quả**

```
✅ Issue #[number] đã tạo:

  GSU26SE55/$REPO#[number] — [$ROLE] $TITLE
  URL: https://github.com/GSU26SE55/$REPO/issues/[number]
  Sprint Board: https://github.com/orgs/GSU26SE55/projects/3

Tiếp theo — khi sẵn sàng implement:
  cd ~/Documents/GSU26SE55/$REPO && git pull && claude
  /kltn-plan [number]         ← viết plan, hỏi nếu chưa rõ, post context vào issue này
  /kltn-implement [number]    ← chạy SAU khi plan đã approved
```
