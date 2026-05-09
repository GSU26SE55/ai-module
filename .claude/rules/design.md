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
  [AI Module — FastAPI]
```

---

## Layer 1: Backend (ASP.NET Core)

Chi tiết rules → [tech/be.md](tech/be.md)

- Auth: JWT, role-based (Admin / Manager / Staff / Customer)
- Battery API: CRUD pin, lịch sử đo lường, ngưỡng cảnh báo
- Ticket API: tạo ticket, cập nhật trạng thái, SLA timer
- AI Bridge: gọi AI module để lấy dự đoán SOH + phân loại trạng thái

**Database:**
- `PostgreSQL` — dữ liệu relational (users, tickets, battery configs)
- `TimescaleDB` — time-series data (sensor readings)
- `Redis` — cache session, pub/sub cho real-time alert

---

## Layer 2: Frontend (ReactJS)

Chi tiết rules → [tech/fe.md](tech/fe.md)

3 portal theo role: Admin / Manager / Staff

**SLA theo ITIL — Priority-based:**
| Priority | SLA | Trigger | Breach action |
|----------|-----|---------|---------------|
| P1 Critical | < 4h | Pin mất điện / nguy cơ an toàn | Reassign Senior + notify Admin |
| P2 High | < 24h | Degradation đáng kể | Manager reassign |
| P3 Standard | < 72h | Bất thường nhẹ / bảo trì định kỳ | Manager review |

- Priority do Manager gán khi triage, **không thay đổi** trong vòng đời ticket
- Breach → escalate thêm nhân lực/cấp bậc, không extend deadline

---

## Layer 3: Mobile App (React Native/Expo)

Chi tiết rules → [tech/mobile.md](tech/mobile.md)

- Real-time sensor display (polling hoặc WebSocket)
- Notification push khi có cảnh báo
- Tạo ticket hỗ trợ từ app
- Xem lịch sử + prediction chart

---

## Priority Change Policy ⚠️

Priority do Manager gán khi triage. Trong vòng đời ticket:

| Ai được phép thay đổi | Điều kiện |
|-----------------------|-----------|
| Manager, Admin | Có thể thay đổi bất kỳ lúc nào |
| Staff | KHÔNG được thay đổi |

**Khi priority thay đổi:**
1. Log vào bảng `audit_logs`: `(who, when, ticket_id, field="Priority", old_value, new_value)`
2. SLA timer **RESET** về 0 theo priority mới
3. Notification gửi tới Staff được assign + Manager phụ trách

**Breach action (SLA timer hết):**
- Không extend deadline — escalate thêm nhân lực / cấp bậc
- Log breach vào `audit_logs` với `field="SLABreach"`

---

## AI Module (FastAPI + PyTorch)

Chi tiết rules → [tech/ai.md](tech/ai.md)

2 core model (không thêm):
1. **LSTM/CNN-LSTM** — dự đoán SOH (State of Health)
2. **Isolation Forest** — phát hiện bất thường

Output: Classification (Normal / Degrading / Failed) + SOH % + confidence score