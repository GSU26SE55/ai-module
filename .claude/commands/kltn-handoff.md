Tạo file bàn giao công việc cho ticket, dùng khi cần chuyển task cho người khác hoặc tạm dừng dài ngày.

Ticket: `$ARGUMENTS`

**Bước 1 — Đọc trạng thái hiện tại**
Dùng Read tool đọc `logs/$ARGUMENTS/plan.md`. Thu thập:
- Status hiện tại
- Danh sách Steps: cái nào đã `[x]`, cái nào còn `[ ]`
- Branch name từ git
- Các file đã tạo/sửa

```bash
git branch --show-current
git log main...HEAD --oneline
git status
```

**Bước 2 — Ghi file handoff**
Tạo `logs/$ARGUMENTS/handoff.md` với nội dung:

```markdown
# HANDOFF — KAN-XX: [Tên ticket]

## Thông tin bàn giao
- **Người bàn giao:** [tên từ CLAUDE.local.md]
- **Ngày bàn giao:** YYYY-MM-DD
- **Branch:** feature/KAN-XX-ten-tinh-nang
- **Status hiện tại:** [PLANNING / IN_PROGRESS / REVIEWING / TESTING / SHIPPED]

## Tiến độ Steps

[copy nguyên từ ## Steps trong plan.md — giữ nguyên dấu [x] / [ ]]

**Tóm tắt:** Đã hoàn thành X / Y bước.

## Những gì đã làm
[Mô tả ngắn các bước đã xong, kết quả, file đã tạo]

## Những gì còn lại
[Liệt kê các bước chưa xong theo thứ tự ưu tiên]

## Known Issues / Blockers
- [ ] [Vấn đề đang gặp phải, nếu có]
- [ ] [Dependency chưa có, nếu có]

## Hướng dẫn tiếp tục
1. Checkout branch: `git checkout feature/KAN-XX-ten-tinh-nang`
2. Pull latest: `git pull origin feature/KAN-XX-ten-tinh-nang`
3. Mở Claude Code → gõ `/kltn-task $ARGUMENTS` → Claude sẽ đọc plan và tiếp tục từ bước còn lại

## Ghi chú thêm
[Thông tin quan trọng mà người tiếp nhận cần biết: môi trường, config, context kỹ thuật...]
```

**Bước 3 — Commit handoff**
```bash
git add logs/$ARGUMENTS/handoff.md
git commit -m "docs($ARGUMENTS): thêm handoff file"
git push origin HEAD
```

**Bước 4 — Thông báo**
Dùng `mcp__jira__jira_add_comment` để add comment vào Jira ticket:
"Đã tạo handoff file tại `logs/$ARGUMENTS/handoff.md`. Branch: [branch name]. Tiến độ: X/Y bước hoàn thành."
