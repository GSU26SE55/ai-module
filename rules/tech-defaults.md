# Tech Defaults — Stack mặc định

## Backend

| Quyết định | Lựa chọn | Lý do |
|------------|----------|-------|
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

## Frontend (Web)

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Framework | ReactJS 18 | — |
| State | Zustand | Nhẹ hơn Redux cho scale này |
| HTTP | Axios | Interceptors cho auth token |
| UI | shadcn/ui + Tailwind | Nhất quán, không custom từ đầu |
| Charts | Recharts | Time-series charts đơn giản |

## Mobile

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Framework | React Native (Expo) | Không cần native build phức tạp |
| Navigation | Expo Router | File-based routing |
| HTTP | Axios (shared config với Web) | — |

## AI/ML

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Language | Python 3.11 | — |
| ML Framework | PyTorch | LSTM/CNN-LSTM |
| Anomaly | scikit-learn Isolation Forest | Đủ cho scope capstone |
| Serving | FastAPI | REST endpoint cho BE gọi |
| Dataset | NASA Ames (ưu tiên) | CALCE backup |

## DevOps

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Container | Docker Compose | Local dev + staging |
| CI/CD | GitHub Actions | Auto test + build |
| Hosting | TBD | Deploy cuối Sprint 8 |

---

## Nguyên tắc

- Không thêm dependency mới nếu stack hiện tại đủ giải quyết
- Ưu tiên thứ đã được team dùng quen, không học công nghệ mới giữa dự án
- IoT (MQTT, broker) chỉ thêm vào Sprint 8 nếu core hoàn thành
