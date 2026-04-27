# Skill: /kltn-team

## Mô tả
Kiểm tra nhanh toàn bộ trạng thái team GSU26SE55: Jira tracking, sau đó xuất báo cáo QA theo chuẩn `.claude/agents/reviewer.md`.

## Kích hoạt
Khi người dùng gõ `/kltn-team` hoặc yêu cầu "review team", "kiểm tra tiến độ team", "check tracking".

---

## Quy trình thực hiện

### Bước 1 — Fetch Jira Board qua REST API
  <!-- kiểm tra .env trước khi thực hiện lấy mcp jira -->
**Gọi Jira REST API v3:**

```bash
AUTH="$JIRA_EMAIL:$JIRA_API_TOKEN"
BASE="https://fpt-team-d7rg7yak.atlassian.net"

RESULT=$(curl -s -u "$AUTH" -H "Accept: application/json" -H "Content-Type: application/json" \
  -X POST "$BASE/rest/api/3/search/jql" \
  -d '{"jql":"project=KAN ORDER BY duedate ASC","maxResults":100,"fields":["summary","status","assignee","duedate","issuetype"]}')
```
> Dùng endpoint `/rest/api/3/search/jql` (POST). API Token lưu trong memory, không hardcode.

Thu thập:
- Tasks theo status (To Do / PROCESS / Done / Blocked)
- Assignee, deadline, issuetype
- Tasks overdue + tasks chưa assign

### Bước 2 — Xuất báo cáo

Xuất báo cáo trong conversation:

#### Phần A: Tracking Report
```
## BÁO CÁO TEAM — Sprint [N] — YYYY-MM-DD
### TÓM TẮT ĐIỀU HÀNH
Tổng: X | Done: X | In Progress: X | To Do: X | Blocked: X
[1 câu nhận xét: on-track / at-risk / needs-attention]

### THEO THÀNH VIÊN
| Thành viên | Done | In Progress | Blocked | Ghi chú |
|------------|------|-------------|---------|---------|

### CẢNH BÁO
- Overdue: [danh sách]
- Blocked: [danh sách]
- Không có activity: [danh sách]

### KHUYẾN NGHỊ
- Ngay lập tức (24–48h): ...
- Ngắn hạn (tuần này): ...

### ĐỘ TỰ TIN TỔNG THỂ
[Cao / Trung bình / Thấp]
```

---

## Thông tin cố định

| | |
|-|-|
| **Jira** | https://fpt-team-d7rg7yak.atlassian.net/jira/software/projects/KAN/boards/2 |
| **Output** | Xuất trong conversation |
