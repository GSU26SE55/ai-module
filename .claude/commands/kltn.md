Hiển thị toàn bộ commands của dự án GSU26SE55.

Đọc CLAUDE.local.md để xác định role, sau đó in menu sau:

---

## KLTN Commands — GSU26SE55

### Dev Commands (tất cả thành viên)

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-task KAN-XX` | Bắt đầu làm 1 ticket — đọc ticket → lập plan → code |
| `/kltn-reviewcode` | Review code trước khi ship — xuất PASS / FAIL |
| `/kltn-test KAN-XX` | Kiểm thử sau khi reviewcode PASS — xuất PASS / FAIL |
| `/kltn-ship KAN-XX` | Tạo PR + cập nhật Jira sang IN REVIEW |
| `/kltn-reviewpr KAN-XX` | Review PR của đồng đội — APPROVE hoặc REQUEST CHANGES |

**Luồng chuẩn:**
```
/kltn-task KAN-XX → plan (xác nhận) → code → /kltn-reviewcode → /kltn-test → /kltn-ship KAN-XX
```

**Estimate size:**
- Small (< 2h) — code luôn, có thể bỏ reviewcode + test
- Medium (2–4h) — đi đủ luồng
- Large (> 4h) — hỏi leader trước khi code

---

### Leader Commands (chỉ Trần Minh Trí — SE183109)

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-sprint` | Đầu sprint — phân công task từ Jira, tạo sprint file |
| `/kltn-team` | Báo cáo tiến độ toàn team + QA |
| `/kltn-member [tên]` | Check tiến độ từng người cụ thể |
| `/kltn` | Hiện menu này |

---

### Definition of Done

Ticket được coi là **Done** khi:
1. `/kltn-reviewcode` → PASS
2. `/kltn-test` → PASS
3. PR được ≥ 1 người approve và merged vào main

---

### Quy tắc bắt buộc

- Không push thẳng lên `main` — luôn qua PR
- Không merge PR của chính mình — cần ít nhất 1 người approve
- 1 ticket = 1 branch: `feature/KAN-XX-ten-ngan`
- Commit format: `feat(KAN-XX): mô tả` / `fix` / `refactor` / `test`
- Không thêm package ngoài tech stack trong `.claude/rules/tech-defaults.md`

---

Gõ bất kỳ command nào ở trên để bắt đầu.
