Review PR của đồng đội trước khi approve hoặc request changes.

Ticket/PR: `$ARGUMENTS`

**Bước 1 — Xác định role của bạn**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/review-pr/SKILL.md`
- FE → `.claude/skills/dev/fe/review-pr/SKILL.md`
- AI → `.claude/skills/dev/ai/review-pr/SKILL.md`

**Bước 2 — Lấy thông tin PR, xác định biến làm việc**
```bash
# Nếu $ARGUMENTS là issue number (ví dụ: 12)
gh pr list --search "#$ARGUMENTS in:title OR GH-$ARGUMENTS in:title" \
  --json number,title,url,headRefName

# Nếu $ARGUMENTS là PR number — dùng trực tiếp
gh pr view $ARGUMENTS --json number,title,url,headRefName,state
```

Từ output trên, ghi nhớ để dùng xuyên suốt:
- `$PR_NUMBER` — số PR nguyên (ví dụ: `42`)
- `$ISSUE_NUMBER` — issue number (ví dụ: `12`), trích từ branch `feature/GH-12-...`

**Bước 3 — Lấy diff và review**
```bash
gh pr diff $PR_NUMBER
```
Chạy checklist theo role skill file (Bước 1), xuất kết quả:

```
## BÁO CÁO PR REVIEW — GH-$ISSUE_NUMBER — YYYY-MM-DD
### Reviewer: [tên bạn từ CLAUDE.local.md]
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
Dừng ở đây. Thông báo author sửa và push lại, rồi tag reviewer để review lại.

---

**Nếu KẾT LUẬN = APPROVE:**
```bash
gh pr review $PR_NUMBER --approve --body "LGTM ✅ — [1 câu tóm tắt]"
```
Dừng ở đây. Author sẽ chạy `/kltn-complete $ISSUE_NUMBER` để tạo handoff và merge.
