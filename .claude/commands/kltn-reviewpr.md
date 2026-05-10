Review PR của đồng đội trước khi approve merge.

Ticket/PR: `$ARGUMENTS`

**Bước 1 — Xác định role của bạn**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/review-pr/SKILL.md`
- FE → `.claude/skills/dev/fe/review-pr/SKILL.md`
- AI → `.claude/skills/dev/ai/review-pr/SKILL.md`

**Bước 2 — Lấy thông tin PR, xác định biến làm việc**
```bash
# Nếu $ARGUMENTS là ticket ID (KAN-XX)
gh pr list --search "$ARGUMENTS in:title" --json number,title,url,headRefName

# Nếu $ARGUMENTS là PR number — dùng trực tiếp
gh pr view $ARGUMENTS --json number,title,url,headRefName,state
```

Từ output trên, ghi nhớ 3 giá trị để dùng xuyên suốt các bước sau:
- `$PR_NUMBER` — số PR nguyên (ví dụ: `42`)
- `$BRANCH_NAME` — headRefName (ví dụ: `feature/KAN-12-battery-crud`)
- `$TICKET_ID` — ticket ID trích từ branch hoặc title (ví dụ: `KAN-12`)

> Dùng `$PR_NUMBER` cho tất cả `gh` command, không dùng `$ARGUMENTS` trực tiếp.

**Bước 3 — Lấy diff và review**
```bash
gh pr diff $PR_NUMBER
```
Chạy checklist theo role skill file (Bước 1), xuất kết quả:

```
## BÁO CÁO PR REVIEW — KAN-XX — YYYY-MM-DD
### Reviewer: [tên bạn]
### TÓM TẮT
[1–2 câu về PR]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### KHUYẾN NGHỊ
- Ngay lập tức: ...

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[APPROVE / REQUEST CHANGES] — Độ tự tin: [Cao / Trung bình / Thấp]
```

---

**Nếu KẾT LUẬN = REQUEST CHANGES:**
```bash
gh pr review $PR_NUMBER --request-changes --body "[mô tả vấn đề cần sửa]"
```
Không merge. Chờ author sửa và push lại.

---

**Nếu KẾT LUẬN = APPROVE** — thực hiện tuần tự các bước sau:

**Bước 4 — Tạo handoff TRƯỚC khi merge (commit lên feature branch)**
```bash
git fetch origin
git checkout $BRANCH_NAME
git pull origin $BRANCH_NAME
```

Dùng Edit tool cập nhật `logs/$TICKET_ID/plan.md`:
- `Status: SHIPPED` → `Status: MERGED`
- `Cập nhật lần cuối` → ngày hôm nay

Dùng Write tool tạo `logs/$TICKET_ID/handoff.md`:

```markdown
# HANDOFF — KAN-XX: [Tên ticket]

## Thông tin
- **Người thực hiện:** [author từ git log]
- **Reviewer:** [tên reviewer từ CLAUDE.local.md]
- **Ngày merge:** YYYY-MM-DD
- **Status:** MERGED ✅
- **PR:** [URL PR từ Bước 2]
- **Branch đã xóa:** feature/KAN-XX-ten-tinh-nang

## Tiến độ Steps
[Copy nguyên ## Steps từ plan.md — tất cả phải [x]]

## Những gì đã làm
[Tóm tắt từ danh sách "Các file sẽ tạo/sửa" trong plan.md]

## Kết quả
- reviewcode: PASS
- test: PASS
- PR: merged vào main

## Ghi chú
[Bất kỳ thông tin quan trọng nào cần lưu lại cho tham khảo sau]
```

```bash
git add logs/$TICKET_ID/
git commit -m "docs($TICKET_ID): ticket merged — thêm handoff file"
git push origin $BRANCH_NAME
```

**Bước 5 — Approve & Merge PR**
```bash
git checkout main
gh pr review $PR_NUMBER --approve --body "LGTM ✅"
gh pr merge $PR_NUMBER --merge --delete-branch
git pull origin main
```

**Bước 6 — Cập nhật Jira → Done**
Dùng `mcp__jira__jira_transition` để chuyển ticket sang **Done**.
Dùng `mcp__jira__jira_add_comment` để add comment: "PR merged và approved bởi [tên reviewer] — [ngày hôm nay]."
