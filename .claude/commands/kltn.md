Hiển thị toàn bộ commands của dự án GSU26SE55.

Đọc CLAUDE.local.md để xác định role, sau đó in menu sau:

---

## KLTN Commands — GSU26SE55

### Thông tin & Setup

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-setup` | Mới join project — xem hướng dẫn setup lần đầu (1 lần duy nhất) |
| `/kltn-guide` | Xem hướng dẫn sử dụng hàng ngày, danh sách lệnh, quy tắc |
| `/kltn` | Hiện menu này |

---

### Dev Commands (tất cả thành viên)

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-plan GH-XX` | Hiểu rõ task — đọc issue, hỏi nếu chưa rõ, lập plan, chờ approve |
| `/kltn-implement GH-XX` | Implement — **yêu cầu plan đã approved** (chạy sau `/kltn-plan`) |
| `/kltn-reviewcode` | Review code trước khi ship — xuất PASS / FAIL |
| `/kltn-test GH-XX` | Kiểm thử sau khi reviewcode PASS — xuất PASS / FAIL |
| `/kltn-ship GH-XX` | Tạo PR + cập nhật label → reviewing |
| `/kltn-reviewpr GH-XX` | Review PR của đồng đội — APPROVE hoặc REQUEST CHANGES (chỉ reviewer) |
| `/kltn-complete GH-XX` | Sau khi PR được APPROVE: tạo handoff → push → merge → done (chỉ author) |

**Luồng chuẩn (bắt buộc với MỌI task):**
```
[Author]   /kltn-plan GH-XX  → đọc issue → hỏi nếu chưa rõ → plan.md → approve
[Author]   /kltn-implement GH-XX  → implement từng bước trong plan
           → /kltn-reviewcode → /kltn-test GH-XX → /kltn-ship GH-XX
[Reviewer] /kltn-reviewpr GH-XX → APPROVE hoặc REQUEST CHANGES
[Author]   /kltn-complete GH-XX → handoff → merge → Done
```

**Ví dụ thực tế (issue #42):**
```
/kltn-plan 42         ← đọc issue, hỏi nếu scope/approach chưa rõ, tạo plan
/kltn-implement 42         ← implement theo plan đã approve
/kltn-ship 42         ← tạo PR, label → reviewing
/kltn-complete 42     ← merge PR, label → done
```

---

### Leader Commands (chỉ Trần Minh Trí — SE183109)

| Command | Dùng khi nào |
|---------|-------------|
| `/kltn-sprint` | Đầu sprint — tạo GitHub Issues trong sub-repos, phân công assignee |
| `/kltn-team` | Báo cáo tiến độ toàn team |
| `/kltn-member [tên]` | Check tiến độ từng người cụ thể |

---

### Definition of Done

Ticket được coi là **Done** khi **đủ cả 3**:
1. `/kltn-reviewcode` → PASS
2. `/kltn-test GH-XX` → PASS
3. PR được ≥ 1 người approve và merged vào main

---

### Quy tắc bắt buộc

- Không push thẳng lên `main` — luôn qua PR
- Không merge PR của chính mình — cần ít nhất 1 người approve
- 1 issue = 1 branch: `feature/GH-[number]-ten-ngan`
- Commit format: `feat(#42): mô tả` / `fix(#42)` / `refactor(#42)` / `test(#42)`
- PR body phải có `Closes #[number]` để GitHub tự close issue khi merge
- Không thêm package ngoài tech stack trong `.claude/rules/tech/{be,fe,mobile,ai}.md`

---

Gõ `/kltn-guide` để xem hướng dẫn đầy đủ hoặc bất kỳ command nào ở trên để bắt đầu.
