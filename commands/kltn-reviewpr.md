Review PR của đồng đội trước khi approve merge.

Ticket/PR: `$ARGUMENTS`

**Bước 1 — Xác định role của bạn**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/review-pr.md`
- FE → `.claude/skills/dev/fe/review-pr.md`
- AI → `.claude/skills/dev/ai/review-pr.md`

**Bước 2 — Lấy diff PR**
```bash
gh pr diff $ARGUMENTS
```

**Bước 3 — Chạy checklist theo role, xuất kết quả**
```
## BÁO CÁO PR REVIEW — KAN-XX
### TÓM TẮT
[1–2 câu về PR]

### PHÂN TÍCH
🔴 Critical: ...
🟡 Warning: ...
✅ Pass: ...

### KHUYẾN NGHỊ
- Ngay lập tức: ...
- Nếu cần: ...

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[APPROVE / REQUEST CHANGES] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Nếu APPROVE → approve trên GitHub.
Nếu REQUEST CHANGES → comment lên PR, không approve.
