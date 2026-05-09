Làm việc trên Jira ticket được chỉ định.

**Bước 1 — Xác định role của bạn**
Đọc CLAUDE.local.md. Nếu có **Dev Role** → dùng Dev Role. Nếu chỉ có Role → dùng Role đó.
- BE → `.claude/skills/dev/be/task.md`
- FE → `.claude/skills/dev/fe/task.md`
- AI → `.claude/skills/dev/ai/task.md`

**Bước 2 — Đọc context**
Fetch Jira ticket: `$ARGUMENTS`

**Bước 3 — Lập Implementation Plan & viết plan.md (bắt buộc)**
Viết file `logs/KAN-XX/plan.md` (thay KAN-XX bằng ticket ID thực tế) với nội dung:
- **Scope:** Ticket yêu cầu làm gì, output mong đợi là gì
- **Files:** Danh sách file sẽ tạo mới / chỉnh sửa
- **Approach:** Mô tả ngắn thuật toán, data flow, hoặc API design
- **Edge cases:** Các trường hợp cần xử lý đặc biệt
- **Estimate:** Small / Medium / Large theo ngưỡng:
  - **Small** (< 2 giờ): code luôn
  - **Medium** (2–4 giờ): code luôn
  - **Large** (> 4 giờ): code luôn sau khi user xác nhận plan

Chờ xác nhận plan (hoặc người dùng gõ "ok" / "proceed") trước khi bắt đầu code.

**Bước 4 — Thực hiện theo đúng skill file của role**
Tạo branch, implement theo plan đã xác nhận, self-review, commit.
