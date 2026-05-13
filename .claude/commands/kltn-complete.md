Hoàn tất task sau khi PR được approve: tạo handoff → push lên branch → merge PR → close GitHub Issue.
Chỉ người viết code (author) mới chạy lệnh này.

Issue number: `$ARGUMENTS`

**Bước 1 — Xác định branch hiện tại và PR**

Kiểm tra branch đang đứng:
```bash
git branch --show-current
```

- Nếu đang đứng ở `feature/GH-$ARGUMENTS-...` → dùng luôn branch này.
- Nếu đang đứng ở `main` → liệt kê toàn bộ branch:
  ```bash
  git branch
  ```
  Sau đó `git checkout feature/GH-$ARGUMENTS-...` trước khi tiếp tục.

Lấy thông tin PR — ưu tiên đọc từ `logs/GH-$ARGUMENTS/plan.md` (trường `PR:`):
```bash
gh pr list --search "#$ARGUMENTS in:title OR GH-$ARGUMENTS in:title" \
  --json number,title,url,headRefName,reviewDecision
```

Ghi nhớ:
- `$PR_NUMBER` — số PR nguyên
- `$BRANCH_NAME` — headRefName
- `$ISSUE_NUMBER` = `$ARGUMENTS`

Kiểm tra `reviewDecision`:
- `APPROVED` → tiếp tục Bước 2
- `CHANGES_REQUESTED` → **DỪNG**. Đọc review comments, sửa code, commit, push, rồi báo reviewer review lại.
- `REVIEW_REQUIRED` / chưa có review → **DỪNG**. Chờ đồng đội chạy `/kltn-reviewpr $ARGUMENTS`.

**Bước 2 — Checkout branch và pull latest**
```bash
git fetch origin
git checkout $BRANCH_NAME
git pull origin $BRANCH_NAME
```

**Bước 3 — Tạo handoff file**
Dùng Edit tool cập nhật `logs/GH-$ISSUE_NUMBER/plan.md`:
- Đổi dòng `Status: SHIPPED` → `Status: MERGED`
- Đổi `Cập nhật lần cuối` → ngày hôm nay

Dùng Write tool tạo `logs/GH-$ISSUE_NUMBER/handoff.md`:

```markdown
# HANDOFF — GH-[number]: [Tên issue]

## Thông tin
- **Người thực hiện:** [tên từ CLAUDE.local.md]
- **Reviewer:** [tên reviewer — lấy từ `gh pr view $PR_NUMBER --json reviews`]
- **Ngày merge:** YYYY-MM-DD
- **Status:** MERGED ✅
- **Issue:** #[number]
- **PR:** [URL PR từ Bước 1]
- **Branch:** $BRANCH_NAME

## Tiến độ Steps
[Copy nguyên ## Steps từ plan.md — tất cả phải [x]]

## Những gì đã làm
[Tóm tắt từ danh sách Files trong plan.md]

## Kết quả
- reviewcode: PASS
- test: PASS
- reviewpr: APPROVED
- PR: merged vào main

## Ghi chú
[Thông tin kỹ thuật quan trọng: migration đã chạy, breaking change, cần update config...]
```

**Bước 4 — Commit và push handoff lên branch**

```bash
git add logs/GH-$ISSUE_NUMBER/
git commit -m "docs(#$ISSUE_NUMBER): task merged — thêm handoff file"
git push origin $BRANCH_NAME
```

**Bước 5 — Merge PR**
```bash
gh pr merge $PR_NUMBER --merge
```

Nếu lệnh trên **thất bại**, dừng ngay và thực hiện recovery:

```
❌ GH PR MERGE THẤT BẠI — Recovery steps:
1. Kiểm tra lý do:
   gh pr view $PR_NUMBER --json state,mergeable,mergeStateStatus

2. Nếu merge conflict → resolve conflict trên branch, push lại, rồi thử lại:
   git checkout $BRANCH_NAME
   git merge main
   # ... fix conflict ...
   git push origin $BRANCH_NAME
   gh pr merge $PR_NUMBER --merge

3. Nếu branch protection rule chưa pass (CI fail) → chờ CI xanh rồi thử lại.

4. Khôi phục trạng thái plan.md về SHIPPED:
   - Mở logs/GH-$ISSUE_NUMBER/plan.md
   - Đổi Status: MERGED → Status: SHIPPED
   - Commit + push

5. Không thực hiện Bước 6 khi merge chưa thành công.
```

Nếu merge **thành công**:
```bash
git checkout main
git pull origin main
```

**Bước 6 — Close GitHub Issue + cập nhật label**
*(Chỉ thực hiện sau khi Bước 5 thành công)*

> **Lưu ý:** Nếu PR body có `Closes #$ISSUE_NUMBER`, GitHub tự close issue khi merge. Bước này xử lý label `status: done` và comment handoff.

```bash
# Cập nhật label: status: reviewing → status: done
gh issue edit $ISSUE_NUMBER \
  --remove-label "status: reviewing" \
  --add-label "status: done"

# Comment tóm tắt kết quả
gh issue comment $ISSUE_NUMBER --body "## ✅ DONE — GH-$ISSUE_NUMBER

**PR #$PR_NUMBER** đã merge vào main.
**Reviewer:** [tên reviewer]
**Ngày merge:** $(date +%Y-%m-%d)

Handoff chi tiết tại: \`logs/GH-$ISSUE_NUMBER/handoff.md\`"

# Đảm bảo issue đã closed (phòng trường hợp PR không có Closes #)
gh issue close $ISSUE_NUMBER 2>/dev/null || true
```
