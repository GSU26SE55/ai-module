---
name: task
description: Tạo GitHub Issue mới cho AI module — điền title, type, priority, mô tả, gán assignee, thêm vào sprint milestone. Kết quả là issue ở trạng thái status:init, sẵn sàng để /kltn-plan.
argument-hint: []
allowed-tools: Bash, Read
---

# Skill: /kltn-task (AI)

## Kích hoạt
`/kltn-task` — tạo GitHub Issue mới cho AI module.

---

## Bước 1 — Kiểm tra CLAUDE.local.md

```bash
cat .claude/CLAUDE.local.md 2>/dev/null || echo "FILE_NOT_FOUND"
```

Xác nhận file có đủ: **Tên**, **MSSV**, **Role chính**, **Role phụ**.
Nếu thiếu → dừng, yêu cầu tạo file trước.

---

## Bước 2 — Kiểm tra sprint hiện tại

```bash
gh milestone list --state open
```

Ghi nhận tên milestone đang mở (ví dụ: `Sprint 4`).
Nếu không có milestone nào → hỏi user trước khi tiếp tục.

---

## Bước 3 — Thu thập thông tin từ user

Hỏi lần lượt, chờ user trả lời từng câu:

```
1. Tiêu đề issue (ngắn gọn, bắt đầu bằng động từ):
   Ví dụ: "Implement SOH prediction endpoint"

2. Loại task:
   [1] feat     — tính năng mới
   [2] fix      — sửa lỗi
   [3] refactor — cải thiện code, không đổi behavior
   [4] test     — viết / cải thiện tests
   [5] docs     — tài liệu, README

3. Priority:
   [1] P1: Critical (4h SLA)  — lỗi nghiêm trọng, ảnh hưởng core function
   [2] P2: High (24h SLA)     — tính năng quan trọng cần sớm
   [3] P3: Standard (72h SLA) — task thông thường

4. Mô tả ngắn — issue này cần làm gì? (2–5 câu)
   (Có thể bỏ trống để dùng template mặc định)

5. Acceptance criteria — done khi nào?
   (Có thể bỏ trống để dùng template mặc định)
```

---

## Bước 4 — Tạo GitHub Issue

Sau khi có đủ thông tin, tạo issue:

```bash
gh issue create \
  --title "[TYPE] TITLE" \
  --body "$(cat <<'BODY'
## Mô tả
DESCRIPTION

## Acceptance Criteria
- [ ] ...
- [ ] ...

## Technical Notes
- Stack: Python 3.11 · PyTorch · FastAPI · scikit-learn
- Seed: `random_seed = 42` bắt buộc
- Inference latency target: < 100ms

## Workflow
Plan: \`/kltn-plan ISSUE_NUMBER\`
BODY
)" \
  --label "role: AI" \
  --label "priority: PRIORITY_LABEL" \
  --label "type: TYPE" \
  --label "status: init" \
  --milestone "SPRINT_NAME" \
  --assignee "@me"
```

**Mapping giá trị user chọn → label:**

| User chọn | `--label` tương ứng |
|-----------|-------------------|
| feat | `type: feat` |
| fix | `type: fix` |
| refactor | `type: refactor` |
| test | `type: test` |
| docs | `type: docs` |
| P1 | `priority: P1: Critical (4h)` |
| P2 | `priority: P2: High (24h)` |
| P3 | `priority: P3: Standard (72h)` |

**Format title:** `[type] Tiêu đề user nhập`
Ví dụ: `[feat] Implement SOH prediction endpoint`

---

## Bước 5 — Xác nhận kết quả

Sau khi tạo xong:

```bash
gh issue view NUMBER --json number,title,labels,milestone,assignees
```

In ra cho user:

```
✅ Issue #NUMBER đã tạo thành công

  Tiêu đề : [type] TITLE
  Labels   : role: AI · type: TYPE · priority: PRIORITY · status: init
  Sprint   : SPRINT_NAME
  Assignee : @me
  URL      : https://github.com/ORG/REPO/issues/NUMBER

Bước tiếp theo:
  /kltn-plan NUMBER   ← lập plan trước khi implement
```

---

## Không được
- Tạo issue mà không có milestone — issue sẽ không xuất hiện trên Sprint Board
- Bỏ label `status: init` — Sprint Board dùng label này để track
- Bỏ label `role: AI` — reviewer không biết đây là AI task
- Tạo issue trùng lặp — kiểm tra `gh issue list --label "role: AI"` nếu không chắc
