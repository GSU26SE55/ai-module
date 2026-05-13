# Memory — Ngữ cảnh bổ sung GSU26SE55

> File này chứa thông tin **không** có trong rules/tech/ hay CLAUDE.md.
> Team + kiến trúc: xem CLAUDE.md | Tech rules: xem rules/tech/*.md

---

## Timeline chi tiết (8 Sprints)

| Sprint | Thời gian | Nội dung chính |
|--------|-----------|----------------|
| Sprint 1 | 11/5 – 1/6 | Tài liệu + thiết kế hệ thống |
| Sprint 2 | 2/6 – 4/6 | Setup BE/FE/Mobile + authentication |
| Sprint 3 | 5/6 – 22/6 | Core battery data APIs |
| Sprint 4 | 23/6 – 6/7 | Ticket management system |
| Sprint 5 | 7/7 – 20/7 | SLA system implementation |
| Sprint 6 | 21/7 – 3/8 | Dashboard + mobile refinement |
| Sprint 7 | 4/8 – 7/8 | System testing toàn diện |
| Sprint 8 | 8/8 – 31/8 | IoT integration + optimization |
| Final | 1/9 – 6/9 | Deployment + chuẩn bị báo cáo |

---

## Dataset công khai

| Dataset | Cells | Ưu tiên | Ghi chú |
|---------|-------|---------|---------|
| NASA Ames Battery Aging | 18650 | **Ưu tiên 1** | nominal = 2.0 Ah |
| CALCE CS2 | Prismatic | Backup | — |
| MIT/Stanford Fast-Charging | 124 cells | Tùy chọn | — |
| Oxford Battery Degradation | — | Tùy chọn | — |

---

## Roster team

| Tên | MSSV | Role chính | Role phụ |
|-----|------|------------|----------|
| Nguyễn Phúc Duy | SE184821 | BE | FE, AI |
| Bùi Phước Thắng | SE180445 | BE | FE, AI |
| Mai Hồng Thái | SE183923 | BE | FE, AI |
| Trần Minh Trí | SE183109 | FE (Leader) | BE, AI |
| Nguyễn Nhật Minh | SE170310 | FE | BE, AI |

> AI là role phụ **chung toàn team** — ai cũng có thể được assign task AI khi cần.

---

## Business Impact

- Giảm 20–30% chi phí bảo trì
- Giảm tới 70% sự cố ngoài kế hoạch
- ROI điển hình: 10:1 đến 30:1

---

## Ghi chú triển khai

- IoT module là **tùy chọn** — chỉ triển khai Sprint 8 nếu core software đã xong
- Ưu tiên 60–70% effort cho core software trước
- GVHD: Trương Long (longt5@fe.edu.vn)
