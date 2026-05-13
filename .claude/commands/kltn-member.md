Xem trạng thái của một thành viên cụ thể. Chỉ dành cho Leader.

Thành viên: `$ARGUMENTS`

**Bước 1 — Map tên → GitHub username**

| Tên | GitHub username |
|-----|----------------|
| Duy / Nguyễn Phúc Duy | [username] |
| Thắng / Bùi Phước Thắng | [username] |
| Thái / Mai Hồng Thái | [username] |
| Trí / Trần Minh Trí | [username] |
| Minh / Nguyễn Nhật Minh | [username] |

*(Leader cập nhật GitHub usernames vào đây khi setup)*

**Bước 2 — Fetch issues được assign (tất cả repos)**

```bash
for REPO in backend frontend mobile ai-module; do
  echo "=== GSU26SE55/$REPO ==="
  gh issue list \
    --repo "GSU26SE55/$REPO" \
    --assignee "$GITHUB_USERNAME" \
    --state all \
    --json number,title,labels,state,createdAt,updatedAt,closedAt,milestone \
    --limit 50
done
```

> Ghi rõ repo nguồn bên cạnh số issue trong báo cáo (ví dụ: `#12 (backend)`).

**Bước 3 — Phân loại và xuất báo cáo**

```
## BÁO CÁO — [Tên thành viên] — YYYY-MM-DD

### Tổng quan
- Role chính: BE / FE / AI
- Sprint hiện tại: Sprint N

### Tasks theo status
✅ Done (closed):
  #123 — [Tên issue] — merged YYYY-MM-DD

🔨 Implementing (status: implementing):
  #124 — [Tên issue] — started YYYY-MM-DD

👀 Reviewing (status: reviewing):
  #125 — [Tên issue] — PR #45, waiting since YYYY-MM-DD

📋 Init (status: init, chưa bắt đầu):
  #126 — [Tên issue]

### Nhận xét
- Tiến độ so với sprint plan: [Đúng hạn / Chậm / Nhanh]
- Issues cần chú ý: ...

### Khuyến nghị
[Action items cụ thể cho thành viên này]
```
