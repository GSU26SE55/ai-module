Chạy kiểm thử cho ticket được chỉ định.

Ticket: `$ARGUMENTS`

**Bước 1 — Cập nhật status**
Dùng Edit tool cập nhật `logs/GH-$ARGUMENTS/plan.md`:
- `Status: REVIEWING` → `Status: TESTING`
- `Cập nhật lần cuối` → ngày hôm nay

**Bước 2 — Xác định scope và chạy test**
Xác định role từ CLAUDE.local.md → đọc và thực hiện đúng theo skill tương ứng:
- BE → `.claude/skills/dev/be/test/SKILL.md`
- FE → `.claude/skills/dev/fe/test/SKILL.md`
- AI → `.claude/skills/dev/ai/test/SKILL.md`

> Nếu ticket liên quan nhiều layer (ví dụ BE + AI) → spawn `.claude/agents/tester.md` để test cross-service thay vì inline.

**Bước 3 — Xuất báo cáo**
```
## TEST REPORT — GH-$ARGUMENTS — YYYY-MM-DD
### Scope: [BE / FE / AI]
### Môi trường: local

### TÓM TẮT
[1–2 câu về kết quả chung]

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|

### Coverage
- Line coverage: X% (target: BE ≥ 80% / FE ≥ 70% / AI ≥ 85%)

### Bugs tìm được
- 🔴 [Critical] ...

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

**Bước 4 — Lưu log test**
Lưu toàn bộ báo cáo vào `logs/GH-$ARGUMENTS/test.md`.
Nếu folder chưa tồn tại → tạo mới.

Nếu FAIL → sửa bugs → cập nhật `Status` về `IN_PROGRESS` → chạy lại `/kltn-reviewcode` → `/kltn-test`.
Nếu PASS → nhắc user chạy `/kltn-ship $ARGUMENTS`.
