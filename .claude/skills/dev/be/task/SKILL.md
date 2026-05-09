# Skill: /kltn-task (BE)

## Kích hoạt
`/kltn-task KAN-XX` — làm việc trên Jira ticket phía Backend.

---

## Quy trình

### Bước 1 — Đọc ticket
Fetch từ Jira, xác định:
- Scope: API mới, chỉnh sửa logic, thêm DB schema, hay tích hợp AI module?
- Input/output của endpoint là gì?
- Cần migration không?

### Bước 2 — Lập Implementation Plan & viết plan.md

Phân tích ticket và viết file plan tại `logs/KAN-XX/plan.md` với nội dung:

```markdown
# Plan — KAN-XX: [Tên ticket]

## Mục tiêu
[Ticket yêu cầu làm gì, endpoint / logic nào]

## Các file sẽ tạo/sửa
| File | Hành động | Mô tả |
|------|-----------|-------|
| Controllers/XxxController.cs | create/modify | ... |
| Services/IXxxService.cs | create/modify | ... |

## Approach
[Data flow: request → validation → service → DB → response]

## Dependencies & Edge Cases
- Auth/role check, validation lỗi, DB constraint, null handling
- Cần migration không?

## Ước tính
- Size: Small / Medium / Large
- Thời gian: X giờ
```

> **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi làm bất cứ bước nào tiếp theo.**
> **TUYỆT ĐỐI KHÔNG CODE khi chưa có xác nhận. Không có ngoại lệ, dù ticket nhỏ đến đâu.**

### Bước 3 — Tạo branch
```bash
git checkout -b feature/KAN-XX-ten-tinh-nang
```

### Bước 4 — Implement theo đúng layer

```
Controller/     ← nhận request, validate input, gọi Service, trả response
│                 KHÔNG chứa business logic
Service/        ← toàn bộ business logic
│                 KHÔNG gọi DbContext trực tiếp
Repository/     ← truy vấn DB qua EF Core
│                 KHÔNG chứa logic
DTOs/           ← request/response models + FluentValidation
Migrations/     ← chỉ tạo qua: dotnet ef migrations add
```

**Khi nào dùng TimescaleDB vs PostgreSQL:**
- Sensor readings, time-series data → **TimescaleDB**
- Users, tickets, configs → **PostgreSQL thường**

**Khi nào dùng Redis:**
- Session / auth token cache
- Pub/sub cho real-time alert

### Bước 5 — Tự kiểm tra trước commit
- Endpoint cần auth đã có `[Authorize]`
- Role check đúng (Admin / Manager / Staff)
- Không hardcode connection string, secret, URL
- EF Core query không có N+1 (`Include()` đúng chỗ)
- Response không leak field nhạy cảm (password hash, internal ID...)
- Migration có thể rollback an toàn

### Bước 6 — Commit
```bash
git add <files cụ thể>
git commit -m "feat(KAN-XX): mô tả ngắn"
```

### Bước 7 — Cập nhật Jira
Chuyển ticket sang **IN PROGRESS**.

---

## Không được
- Viết business logic trong Controller
- Gọi DbContext trực tiếp từ Controller hoặc Service
- Hardcode connection string, secret, URL
- Thêm NuGet package chưa có trong tech-defaults
- Tạo migration bằng tay (phải dùng `dotnet ef migrations add`)

---

## Stack BE
ASP.NET Core · EF Core · PostgreSQL / TimescaleDB · Redis · JWT Auth · FluentValidation · Swagger
