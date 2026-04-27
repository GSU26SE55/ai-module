Review code hiện tại trước khi ship.

**Bước 1 — Xác định role**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/code-review.md`
- FE → `.claude/skills/dev/fe/code-review.md`
- AI → `.claude/skills/dev/ai/code-review.md`

**Bước 2 — Lấy diff**
```bash
git diff main...HEAD
```

**Bước 3 — Chạy checklist theo role, xuất kết quả**
```
## BÁO CÁO CODE REVIEW — [branch]
### TÓM TẮT
[1–2 câu về trạng thái tổng thể]

### PHÂN TÍCH
🔴 Critical: ...
🟡 Warning: ...
✅ Pass: ...

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Nếu FAIL → sửa Critical → chạy lại `/kltn-reviewcode`.
