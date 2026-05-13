Review code hiện tại trước khi ship.

**Bước 1 — Xác định role**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/code-review/SKILL.md`
- FE → `.claude/skills/dev/fe/code-review/SKILL.md`
- AI → `.claude/skills/dev/ai/code-review/SKILL.md`

**Bước 2 — Lấy issue number từ branch**
```bash
# Lấy issue number từ tên branch (vd: feature/GH-12-ten → TICKET_ID = GH-12)
git branch --show-current | grep -oE 'GH-[0-9]+'
```
Gọi kết quả là **TICKET_ID** (ví dụ: `GH-12`). Dùng TICKET_ID cho tất cả bước sau.

Nếu không tìm được → hỏi user trước khi tiếp tục.

**Bước 3 — Cập nhật status trong plan**
Dùng Edit tool cập nhật `logs/TICKET_ID/plan.md`:
- `Status: IN_PROGRESS` → `Status: REVIEWING`
- `Cập nhật lần cuối` → ngày hôm nay

**Bước 4 — Lấy diff**
```bash
git diff main...HEAD
```

**Bước 5 — Chạy checklist theo role, xuất kết quả**
```
## BÁO CÁO CODE REVIEW — [branch] — [YYYY-MM-DD]
### TÓM TẮT
[1–2 câu về trạng thái tổng thể]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

**Bước 6 — Lưu log review**
Lưu toàn bộ báo cáo vào `logs/TICKET_ID/review.md`.
Nếu folder chưa tồn tại → tạo mới.

Nếu FAIL → sửa Critical → cập nhật `Status` về `IN_PROGRESS` → chạy lại `/kltn-reviewcode`.
Nếu PASS → nhắc user chạy `/kltn-test TICKET_ID`.
