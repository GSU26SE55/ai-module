# Tech — Backend (.NET)

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Framework | ASP.NET Core Web API (.NET 8) | Team BE quen, hỗ trợ tốt |
| ORM | Entity Framework Core | Code-first, migration dễ |
| Auth | JWT Bearer Token | Stateless, phù hợp mobile + web |
| Validation | FluentValidation | Tách biệt validation logic |
| API Docs | Swagger/OpenAPI | Auto-gen, FE dễ consume |

## Database

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Relational | PostgreSQL 16 | Users, tickets, configs |
| Time-series | TimescaleDB | Battery sensor readings |
| Cache | Redis 7 | Session, pub/sub alerts |
| Migration | EF Core Migrations | Không viết raw SQL migration |

## DevOps

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Container | Docker Compose | Local dev + staging |
| CI/CD | GitHub Actions | Auto test + build |
| Hosting | TBD | Deploy cuối Sprint 8 |

## Nguyên tắc

- Không thêm NuGet package mới nếu stack hiện tại đủ giải quyết — hỏi Leader trước
- Không viết raw SQL migration — dùng EF Core Migrations
- IoT (MQTT, broker) chỉ thêm vào Sprint 8 nếu core hoàn thành
