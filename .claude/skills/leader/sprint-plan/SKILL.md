# Skill: /kltn-sprint

## Mô tả
Lên kế hoạch sprint: fetch toàn bộ Jira tickets, phân công cho từng thành viên theo role, tạo file sprint plan làm context checkpoint cho cả team.

## Kích hoạt
Khi leader gõ `/kltn-sprint` hoặc "lên kế hoạch sprint", "phân công sprint", "plan sprint [N]".

---

## Quy trình thực hiện

### Bước 1 — Fetch Jira tickets chưa assign hoặc To Do
 <!-- kiểm tra .env trước khi thực hiện lấy mcp jira -->
```bash
AUTH="$JIRA_EMAIL:$JIRA_API_TOKEN"
BASE="https://fpt-team-d7rg7yak.atlassian.net"

# Lấy tickets To Do + unassigned
curl -s -u "$AUTH" -H "Accept: application/json" -H "Content-Type: application/json" \
  -X POST "$BASE/rest/api/3/search/jql" \
  -d '{"jql":"project=KAN AND status=\"To Do\" ORDER BY priority DESC","maxResults":100,"fields":["summary","status","assignee","duedate","issuetype","priority","labels"]}'
```

### Bước 2 — Phân loại tickets theo domain

Phân nhóm tickets:
- **BE tasks**: API, database, auth, business logic → assign cho BE Devs (Thắng, Thái)
- **FE tasks**: Web UI, component, routing → assign cho FE Devs (Trí, Minh)
- **AI tasks**: Model, training pipeline, prediction endpoint → assign cho **Nguyễn Phúc Duy** (BE Dev / AI Dev)
- **Cross-cutting**: Docs, deploy, testing → phân đều

### Bước 3 — Đề xuất phân công

Dựa trên:
- Workload hiện tại của từng người (số tickets In Progress)
- Skill phù hợp với ticket
- Deadline của ticket

Xuất đề xuất dạng bảng:

```
## ĐỀ XUẤT PHÂN CÔNG — Sprint [N]

| Ticket | Tóm tắt | Đề xuất assign | Lý do | Deadline |
|--------|---------|----------------|-------|---------|
| KAN-XX | ...     | Nguyễn Phúc Duy | AI task — phụ trách AI module | DD/MM |
```

### Bước 4 — Tạo file sprint plan

Xuất kế hoạch sprint trong conversation:

```markdown
# Sprint N Plan — [DD/MM/YYYY]

## Mục tiêu sprint
[Từ Jira sprint goal hoặc suy ra từ tickets]

## Phân công

### Nguyễn Phúc Duy (BE Dev / AI Dev)
- [ ] KAN-XX: [tóm tắt] — due DD/MM

### Bùi Phước Thắng (BE)
- [ ] ...

### Mai Hồng Thái (BE)
- [ ] ...

### Trần Minh Trí (FE)
- [ ] ...

### Nguyễn Nhật Minh (FE)
- [ ] ...

## Rủi ro
- [Tickets nào có deadline gấp]
- [Thành viên nào có nhiều task nhất]

## Ghi chú
- File này là checkpoint — /kltn-task và /kltn-member đọc file này để tránh re-fetch Jira
```

---

## Nguyên tắc

- **Không tự assign mà không hỏi** — Đây là đề xuất, leader xác nhận trước khi tạo file.
- **Cân bằng workload** — Không để 1 người carry cả sprint.
- **File sprint là context anchor** — Sau khi tạo, các session `/kltn-task` đọc file này thay vì fetch Jira lại.
