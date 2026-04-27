# Skill: /kltn-member

## Mô tả
Xem nhanh trạng thái của một thành viên cụ thể: tickets đang làm, done, blocked, overdue. Dùng để leader nắm tiến độ từng người mà không cần mở Jira.

## Kích hoạt
Khi leader gõ `/kltn-member [tên]` hoặc "check [tên]", "tiến độ của [tên]", "status [tên]".

Ví dụ: `/kltn-member Minh`, `/kltn-member SE170310`

---

## Quy trình thực hiện

### Bước 1 — Xác định thành viên

Mapping tên → MSSV → Jira displayName:

| Tên gọi | MSSV | Jira displayName |
|---------|------|-----------------|
| Duy | SE184821 | Nguyễn Phúc Duy |
| Thắng | SE180445 | Bùi Phước Thắng |
| Thái | SE183923 | Mai Hồng Thái |
| Trí | SE183109 | Trần Minh Trí |
| Minh | SE170310 | Nguyễn Nhật Minh |

### Bước 2 — Fetch tickets của thành viên
  <!-- kiểm tra .env trước khi thực hiện lấy mcp jira -->
```bash
AUTH="$JIRA_EMAIL:$JIRA_API_TOKEN"
BASE="https://fpt-team-d7rg7yak.atlassian.net"

# Thay [DISPLAY_NAME] bằng tên Jira của thành viên
curl -s -u "$AUTH" -H "Accept: application/json" -H "Content-Type: application/json" \
  -X POST "$BASE/rest/api/3/search/jql" \
  -d '{"jql":"project=KAN AND assignee=\"[DISPLAY_NAME]\" ORDER BY duedate ASC","maxResults":50,"fields":["summary","status","duedate","issuetype","updated"]}'
```

### Bước 3 — Xuất báo cáo cá nhân

```
## STATUS — [Tên thành viên] — [YYYY-MM-DD]
### TÓM TẮT
Done: X | In Progress: X | Blocked: X | Overdue: X — [on-track / at-risk / needs-attention]

### ĐANG LÀM
| Ticket | Tóm tắt | Due | Trạng thái |
|--------|---------|-----|-----------|

### HOÀN THÀNH
| Ticket | Tóm tắt | Ngày done |
|--------|---------|-----------|

### ⚠️ CẦN CHÚ Ý
- Overdue: [danh sách]
- Blocked: [danh sách + lý do]
- Stale > 3 ngày: [danh sách]

### KHUYẾN NGHỊ
- Ngay lập tức: ...

### ĐỘ TỰ TIN
[Cao / Trung bình / Thấp]
```

---

## Nguyên tắc

- **Không blame** — Báo cáo trình bày thực tế, không phán xét.
- **Nếu stale > 3 ngày** → gợi ý leader hỏi trực tiếp, không assume blocked.
- **Kết hợp với /kltn-sprint** — Nếu có file sprint, đọc để biết task nào được assign sprint này.
