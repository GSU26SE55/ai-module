# Memory — Thông tin dự án Capstone

## Dự án: Solar Lithium-ion Battery Maintenance Management System

- **Mã dự án:** GSU26SE55
- **Thời gian:** 11/5/2026 – 6/9/2026 (8 sprint + Final Phase)
- **GVHD:** Trương Long (longt5@fe.edu.vn)

---

## Thành viên nhóm

| # | Tên | MSSV | Vai trò |
|---|-----|------|---------|
| 1 | Nguyễn Phúc Duy | SE184821 | BE Dev |
| 2 | Bùi Phước Thắng | SE180445 | BE Dev |
| 3 | Mai Hồng Thái | SE183923 | BE Dev |
| 4 | Trần Minh Trí | SE183109 | FE Dev |
| 5 | Nguyễn Nhật Minh | SE170310 | FE Dev |

---

## Kiến trúc hệ thống

### 1. Mobile App (React Native / Expo)
- Giám sát thông số pin real-time: điện áp, dòng điện, nhiệt độ, dung lượng
- Hiển thị lịch sử dữ liệu + dự đoán AI
- Cảnh báo bất thường tự động
- Tạo và theo dõi support ticket

### 2. Web App (ReactJS)
- **Admin:** quản lý tài khoản, quản lý pin (thực thể chung — mỗi pin có thông số + ngưỡng riêng, không có "loại pin"), định nghĩa SLA
- **Manager:** giám sát hệ thống, theo dõi ticket, báo cáo hiệu suất
- **Staff:** truy cập ticket được giao, cập nhật trạng thái, ghi nhật ký bảo trì
- **SLA theo ITIL:** Level 1 → Level 2 → Level 3 (escalation)

### 3. AI Module
- Phân loại trạng thái pin: Normal / Degrading / Failed
- Phát hiện bất thường (Isolation Forest, Autoencoder)
- Dự đoán State of Health (SOH) — mô hình LSTM, CNN-LSTM
- Benchmarking các mô hình

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | ASP.NET Core Web API (.NET) |
| Frontend | ReactJS |
| Mobile | React Native (Expo) |
| AI/ML | LSTM, CNN-LSTM (time-series) |
| Database | PostgreSQL / TimescaleDB |
| Cache | Redis |
| DevOps | Docker, GitHub Actions (CI/CD) |

---

## Timeline (8 Sprints)

| Sprint | Thời gian | Nội dung |
|--------|-----------|----------|
| Sprint 1 | 11/5 – 1/6 | Tài liệu + thiết kế hệ thống |
| Sprint 2 | 2/6 – 4/6 | Setup BE/FE + authentication |
| Sprint 3 | 5/6 – 22/6 | Core battery data APIs |
| Sprint 4 | 23/6 – 6/7 | Ticket management system |
| Sprint 5 | 7/7 – 20/7 | SLA system implementation |
| Sprint 6 | 21/7 – 3/8 | Dashboard + mobile refinement |
| Sprint 7 | 4/8 – 7/8 | System testing toàn diện |
| Sprint 8 | 8/8 – 31/8 | IoT integration + optimization |
| Final | 1/9 – 6/9 | Deployment + chuẩn bị báo cáo |

---

## Dataset công khai sử dụng

- NASA Ames Battery Aging Dataset (18650 cells)
- CALCE CS2 Battery Dataset (prismatic cells)
- MIT/Stanford Fast-Charging Dataset (124 cells)
- Oxford Battery Degradation Dataset

---

## Business Impact

- Giảm 20–30% chi phí bảo trì
- Giảm tới 70% sự cố ngoài kế hoạch
- ROI điển hình: 10:1 đến 30:1

---

## Ghi chú

- IoT module là **tùy chọn** — chỉ triển khai nếu còn nguồn lực
- Ưu tiên 60–70% cho core software trước
- Phương pháp: Agile/Scrum, sprint 2 tuần
