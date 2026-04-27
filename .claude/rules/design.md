# Design — Kiến trúc hệ thống

## Tổng quan

3 layer độc lập, giao tiếp qua REST API:

```
[Mobile App]  ←→  [Web App]
      ↓               ↓
    [ASP.NET Core Web API]
      ↓               ↓
[PostgreSQL/TimescaleDB]  [Redis Cache]
      ↓
  [AI Module]
```

---

## Layer 1: Backend (ASP.NET Core)

- **Auth:** JWT, role-based (Admin / Manager / Staff / Customer)
- **Battery API:** CRUD pin, lịch sử đo lường, ngưỡng cảnh báo
- **Ticket API:** tạo ticket, cập nhật trạng thái, SLA timer
- **AI Bridge:** gọi AI module để lấy dự đoán SOH + phân loại

**Database design:**
- `PostgreSQL` — dữ liệu relational (users, tickets, battery configs)
- `TimescaleDB` — time-series data (sensor readings theo thời gian)
- `Redis` — cache session, pub/sub cho real-time alert

---

## Layer 2: Frontend (ReactJS)

3 portal theo role:
- **Admin portal** — quản lý user, pin, SLA definition
- **Manager portal** — dashboard tổng quan, báo cáo
- **Staff portal** — ticket queue, maintenance log

**SLA theo ITIL — Priority-based:**
- P1 (Critical): resolve < 4h — pin mất điện / nguy cơ an toàn. Breach → reassign Senior + notify Admin.
- P2 (High): resolve < 24h — degradation đáng kể / hiệu suất giảm. Breach → Manager reassign.
- P3 (Standard): resolve < 72h — bất thường nhẹ / bảo trì định kỳ. Breach → Manager review.
- Priority do Manager gán khi triage, **không thay đổi** trong vòng đời ticket.
- Breach → escalate thêm nhân lực/cấp bậc, không extend deadline.

---

## Layer 3: Mobile App (React Native/Expo)

- Real-time sensor display (polling hoặc WebSocket)
- Notification push khi có cảnh báo
- Tạo ticket hỗ trợ từ app
- Xem lịch sử + prediction chart

---

## AI Module

**Mục tiêu:** 2 core model (không thêm):
1. **LSTM/CNN-LSTM** — dự đoán SOH (State of Health)
2. **Isolation Forest hoặc Autoencoder** — phát hiện bất thường

**Dataset:** Ưu tiên NASA Ames → CALCE nếu cần thêm data.

**Thực tế capstone:** Target accuracy 85–90%, không overpromise 99%+.

**Output:** Classification (Normal / Degrading / Failed) + SOH % + confidence score
