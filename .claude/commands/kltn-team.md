Kiểm tra toàn bộ trạng thái team. Chỉ dành cho Leader.

**Bước 1 — Xác định sprint**

Nếu `$ARGUMENTS` trống → dùng sprint milestone gần nhất đang active.
Nếu có `$ARGUMENTS` → dùng "Sprint $ARGUMENTS".

**Bước 2 — Fetch tất cả issues của sprint (tất cả repos)**

```bash
for REPO in backend frontend mobile ai-module; do
  echo "=== GSU26SE55/$REPO — open ==="
  gh issue list \
    --repo "GSU26SE55/$REPO" \
    --milestone "$SPRINT_NAME" \
    --state open \
    --json number,title,labels,assignees,createdAt,updatedAt \
    --limit 100

  echo "=== GSU26SE55/$REPO — closed ==="
  gh issue list \
    --repo "GSU26SE55/$REPO" \
    --milestone "$SPRINT_NAME" \
    --state closed \
    --json number,title,labels,assignees,closedAt \
    --limit 100
done
```

> Issues nằm rải rác ở 4 repos — khi báo cáo ghi rõ repo nguồn bên cạnh số issue (ví dụ: `#12 (backend)`).

**Bước 3 — Phân loại theo label status**

Từ output, phân loại issues:
- `status: init` → Assigned, chưa bắt đầu
- `status: implementing` → Đang làm
- `status: reviewing` → Đang chờ review PR
- `status: done` (hoặc closed) → Hoàn thành

**Bước 4 — Map theo thành viên**

| GitHub username → Tên thành viên |
|----------------------------------|
| [username] → Nguyễn Phúc Duy (SE184821) |
| [username] → Bùi Phước Thắng (SE180445) |
| [username] → Mai Hồng Thái (SE183923) |
| [username] → Trần Minh Trí (SE183109) — Leader |
| [username] → Nguyễn Nhật Minh (SE170310) |

*(Leader cập nhật GitHub username vào đây khi setup)*

**Bước 5 — Xuất báo cáo**

```
## BÁO CÁO TEAM — [Sprint N] — YYYY-MM-DD

### TÓM TẮT ĐIỀU HÀNH
Tổng: X | ✅ Done: X | 🔨 Implementing: X | 👀 Reviewing: X | 📋 Init: X

### THEO THÀNH VIÊN
| Thành viên | ✅ Done | 🔨 Implementing | 👀 Reviewing | 📋 Init | Ghi chú |
|------------|--------|-----------------|-------------|--------|---------|
| Duy (BE)   | 2      | 1               | 0           | 1      |         |
| Thắng (BE) | 1      | 0               | 1           | 0      | PR #45 chờ review |
| Thái (BE)  | 2      | 1               | 0           | 0      |         |
| Trí (Leader/FE) | 1 | 1              | 0           | 1      |         |
| Minh (FE)  | 0      | 0               | 1           | 1      | ⚠️ chậm so với sprint plan |

### CHI TIẾT ISSUES
| # | Tên | Assignee | Status | Priority |
|---|-----|----------|--------|----------|
| #123 | Battery CRUD | Duy | 🔨 implementing | P2 |
| #124 | Auth login | Trí | ✅ done | P2 |

### KHUYẾN NGHỊ
- **Ngay lập tức (24h):** ...
- **Tuần này:** ...

### RỦI RO & LƯU Ý
- Overdue (sprint deadline gần): #XXX
- Blocked: ...
- PR chờ review lâu (> 1 ngày): #XXX

### ĐỘ TỰ TIN TỔNG THỂ
[Cao / Trung bình / Thấp]
```
