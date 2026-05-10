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

| Tên gọi | MSSV | Jira displayName | Role chính | Role phụ |
|---------|------|-----------------|------------|----------|
| Duy | SE184821 | Nguyễn Phúc Duy | BE | FE, AI |
| Thắng | SE180445 | Bùi Phước Thắng | BE | FE, AI |
| Thái | SE183923 | Mai Hồng Thái | BE | FE, AI |
| Trí | SE183109 | Trần Minh Trí | FE (Leader) | BE, AI |
| Minh | SE170310 | Nguyễn Nhật Minh | FE | BE, AI |

> **AI là role phụ chung** — mọi thành viên đều có thể được assign ticket AI module khi cần.

### Bước 2 — Fetch tickets của thành viên

Dùng Jira MCP (credentials đã cấu hình trong `~/.claude/settings.json`):

```
jira_search: project = KAN AND assignee = "[Jira displayName]" ORDER BY duedate ASC
fields: summary, status, duedate, issuetype, updated
maxResults: 50
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
