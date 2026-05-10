Hoàn tất ticket sau khi PR được approve: tạo handoff → push lên branch → merge PR → update Jira.
Chỉ người viết code (author) mới chạy lệnh này.

Ticket ID: `$ARGUMENTS`

**Bước 1 — Xác định PR và kiểm tra review status**
```bash
gh pr list --search "$ARGUMENTS in:title" --json number,title,url,headRefName,reviewDecision
```

Ghi nhớ:
- `$PR_NUMBER` — số PR nguyên
- `$BRANCH_NAME` — headRefName (ví dụ: `feature/KAN-12-battery-crud`)
- `$TICKET_ID` = `$ARGUMENTS`

Kiểm tra `reviewDecision`:
- `APPROVED` → tiếp tục Bước 2
- `CHANGES_REQUESTED` → **DỪNG**. Đọc review comments, sửa code, commit, push, rồi báo reviewer review lại.
- `REVIEW_REQUIRED` / chưa có review → **DỪNG**. Chờ đồng đội chạy `/kltn-reviewpr $TICKET_ID`.

**Bước 2 — Checkout branch và pull latest**
```bash
git fetch origin
git checkout $BRANCH_NAME
git pull origin $BRANCH_NAME
```

**Bước 3 — Tạo handoff file**
Dùng Edit tool cập nhật `logs/$TICKET_ID/plan.md`:
- Đổi dòng `Status:` → `Status: MERGED`
- Đổi `Cập nhật lần cuối` → ngày hôm nay

Dùng Write tool tạo `logs/$TICKET_ID/handoff.md`:

```markdown
# HANDOFF — KAN-XX: [Tên ticket]

## Thông tin
- **Người thực hiện:** [tên từ CLAUDE.local.md]
- **Reviewer:** [tên reviewer — lấy từ `gh pr view $PR_NUMBER --json reviews`]
- **Ngày merge:** YYYY-MM-DD
- **Status:** MERGED ✅
- **PR:** [URL PR từ Bước 1]
- **Branch đã xóa:** $BRANCH_NAME

## Tiến độ Steps
[Copy nguyên ## Steps từ plan.md — tất cả phải [x]]

## Những gì đã làm
[Tóm tắt từ danh sách "Các file sẽ tạo/sửa" trong plan.md]

## Kết quả
- reviewcode: PASS
- test: PASS
- reviewpr: APPROVED
- PR: merged vào main

## Ghi chú
[Thông tin kỹ thuật quan trọng cần lưu lại: migration đã chạy, breaking change, cần update config...]
```

**Bước 4 — Commit và push handoff lên branch**
```bash
git add logs/$TICKET_ID/
git commit -m "docs($TICKET_ID): ticket merged — thêm handoff file"
git push origin $BRANCH_NAME
```

**Bước 5 — Merge PR**
```bash
gh pr merge $PR_NUMBER --merge --delete-branch
git checkout main
git pull origin main
```

**Bước 6 — Cập nhật Jira → Done**
Dùng `mcp__jira__jira_transition` để chuyển ticket `$TICKET_ID` sang **Done**.
Dùng `mcp__jira__jira_add_comment` để add comment:
"PR #$PR_NUMBER merged vào main. Reviewer: [tên reviewer]. Ngày: [hôm nay]. Handoff tại `logs/$TICKET_ID/handoff.md`."
