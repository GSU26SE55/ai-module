# Skill: /kltn-team

## Mô tả
Kiểm tra nhanh toàn bộ trạng thái team GSU26SE55: GitHub Issues tracking, sau đó xuất báo cáo QA theo chuẩn `.claude/agents/reviewer.md`.

## Kích hoạt
Khi người dùng gõ `/kltn-team` hoặc yêu cầu "review team", "kiểm tra tiến độ team", "check tracking".

---

## Quy trình thực hiện

### Bước 1 — Fetch GitHub Issues

Dùng `gh` CLI để lấy danh sách issues:

```bash
gh issue list --repo <org>/<repo> --state open --json number,title,assignees,labels
```

Thu thập:
- Tasks theo status label (status: init / status: implementing / status: reviewing / status: done)
- Assignee, deadline (milestone), labels (role, priority, type)
- Tasks overdue (milestone due date < today) + tasks chưa assign

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

### RỦI RO & LƯU Ý
- Overdue: [danh sách]
- Blocked: [danh sách]
- Không có activity > 3 ngày: [danh sách]

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
| **GitHub Issues** | https://github.com/<org>/<repo>/issues |
| **Output** | Xuất trong conversation |

## Roster team

| Tên | MSSV | Role chính | Role phụ |
|-----|------|------------|----------|
| Nguyễn Phúc Duy | SE184821 | BE | FE, AI |
| Bùi Phước Thắng | SE180445 | BE | FE, AI |
| Mai Hồng Thái | SE183923 | BE | FE, AI |
| Trần Minh Trí | SE183109 | FE (Leader) | BE, AI |
| Nguyễn Nhật Minh | SE170310 | FE | BE, AI |

Khi xuất báo cáo theo thành viên, ghi rõ role chính trong cột **Ghi chú** nếu thành viên đang làm task ngoài role chính.
