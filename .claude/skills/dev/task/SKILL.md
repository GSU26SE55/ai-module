# Skill: /kltn-task

## Mô tả
Tạo một GitHub Issue nhẹ (skeleton) trong sub-repo tương ứng với role của thành viên. Issue chỉ cần đủ thông tin để xuất hiện trên Sprint Board và được assign. Context chi tiết (plan, AC) sẽ được update vào issue sau khi chạy `/kltn-plan`.

## Kích hoạt
Khi thành viên gõ `/kltn-task` hoặc "tạo task", "tạo issue mới", "new task".

---

## Mapping role → repo (cố định)

| Role | Repo |
|------|------|
| BE | `GSU26SE55/backend` |
| FE | `GSU26SE55/frontend` |
| Mobile | `GSU26SE55/mobile` |
| AI | `GSU26SE55/ai-module` |

---

## Quy trình thực hiện

### Bước 0 — Lấy context người dùng

```bash
# Đọc role từ CLAUDE.local.md
cat .claude/CLAUDE.local.md 2>/dev/null || cat CLAUDE.local.md 2>/dev/null

# Lấy GitHub username đang login
gh api user --jq '.login'

# Lấy milestone đang mở
gh milestone list --repo "GSU26SE55/$REPO" --state open --json title,dueOn \
  --jq '.[] | "\(.title) (due: \(.dueOn // "no date"))"'
```

Ghi nhớ:
- `$MY_ROLE` — Role chính từ `CLAUDE.local.md` → xác định `$REPO`
- `$MY_LOGIN` — GitHub username
- `$SPRINT_NAME` — milestone active (due date sớm nhất)

Nếu thiếu Role chính trong CLAUDE.local.md → dừng và yêu cầu tạo file trước.
Nếu có role phụ → hỏi issue này thuộc role nào để chọn đúng repo.

---

### Bước 1 — Thu thập thông tin tối thiểu

Hỏi user một lần:

```
Cần biết để tạo issue:

1. Tiêu đề: (ví dụ: "Add Battery CRUD API")
2. Mô tả ngắn: task này làm gì? (1–2 câu, có thể để trống nếu chưa rõ)
3. Type: feat / fix / refactor / test / docs / chore  [default: feat]
4. Priority: P1 Critical (4h) / P2 High (24h) / P3 Standard (72h)  [default: P3]
5. Assign cho ai? GitHub username  [default: @$MY_LOGIN]
6. Sprint:  [default: $SPRINT_NAME]
```

> Không hỏi Acceptance Criteria hay technical notes — những thứ đó sẽ được xác định khi `/kltn-plan` và post lên issue sau khi plan approved.

---

### Bước 2 — Kiểm tra trùng lặp

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

### Bước 3 — Xác nhận

```
📋 Xác nhận tạo issue:

  Repo:    GSU26SE55/[repo]
  Title:   [[ROLE]] [title]
  Sprint:  [milestone]
  Assign:  @[assignee]
  Labels:  status: init  |  role: [ROLE]  |  type: [type]  |  priority: [priority]

  Mô tả: [description hoặc "(chưa có — sẽ cập nhật sau khi plan)"]

Gõ "ok" để tạo.
```

> **DỪNG — chờ user xác nhận trước khi chạy `gh issue create`.**

---

### Bước 4 — Tạo issue

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

> **4 nhóm label bắt buộc:**
> `status: init` · `role: *` · `type: *` · `priority: *`

---

### Bước 5 — Xuất kết quả

```
✅ Issue #[number] đã tạo:

  GSU26SE55/[repo]#[number] — [[ROLE]] [title]
  URL: https://github.com/GSU26SE55/[repo]/issues/[number]
  Sprint Board: https://github.com/orgs/GSU26SE55/projects/3

Tiếp theo — khi sẵn sàng implement:
  cd ~/Documents/GSU26SE55/[repo] && git pull && claude
  /kltn-plan [number]         ← viết plan, hỏi nếu chưa rõ, post context vào issue này
  /kltn-implement [number]    ← chạy SAU khi plan đã approved
```

---

## Nguyên tắc

- **Issue lúc tạo là skeleton** — chỉ cần đủ để track trên board. Không ép user điền đầy đủ ngay.
- **Context sẽ được post vào issue sau** — khi `/kltn-plan` chạy xong và plan được approve, plan sẽ được comment vào issue.
- **Tiêu đề bắt đầu bằng `[ROLE]`** — ví dụ `[BE] Add Battery CRUD`, `[FE] Login validation`.
- **Priority default là P3** — không tự nâng lên P1/P2 trừ khi user chỉ định rõ.
- **Không assign cho người khác** nếu user không yêu cầu — default là người tạo.
