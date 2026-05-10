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
| `/kltn-reviewpr KAN-XX` | Review PR của đồng đội — APPROVE hoặc REQUEST CHANGES (chỉ reviewer) |
| `/kltn-complete KAN-XX` | Sau khi PR được APPROVE: tạo handoff → push → merge → update Jira (chỉ author) |

**Luồng chuẩn (bắt buộc với MỌI ticket):**
```
[Author]   /kltn-task KAN-XX → plan (xác nhận) → code → /kltn-reviewcode → /kltn-test KAN-XX → /kltn-ship KAN-XX
[Reviewer] /kltn-reviewpr KAN-XX → APPROVE hoặc REQUEST CHANGES
[Author]   /kltn-complete KAN-XX → handoff → merge → Jira Done
```

**Estimate size:**
- Small (< 2h) — đi đủ luồng, nhanh hơn do scope nhỏ
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

Ticket được coi là **Done** khi **đủ cả 3**:
1. `/kltn-reviewcode` → PASS
2. `/kltn-test KAN-XX` → PASS
3. PR được ≥ 1 người approve và merged vào main

---

### Quy tắc bắt buộc

- Không push thẳng lên `main` — luôn qua PR
- Không merge PR của chính mình — cần ít nhất 1 người approve
- 1 ticket = 1 branch: `feature/KAN-XX-ten-ngan`
- Commit format: `feat(KAN-XX): mô tả` / `fix` / `refactor` / `test`
- Không thêm package ngoài tech stack trong `.claude/rules/tech/{be,fe,mobile,ai}.md`

---

Gõ bất kỳ command nào ở trên để bắt đầu.
