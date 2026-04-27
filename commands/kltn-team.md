Kiểm tra toàn bộ trạng thái team. Chỉ dành cho Leader.

Thực hiện đúng theo `.claude/skills/leader/review-team.md`:
1. Fetch Jira REST API → tracking report toàn team
2. Xuất báo cáo theo format reviewer:
```
## BÁO CÁO TEAM — Sprint [N] — YYYY-MM-DD
### TÓM TẮT ĐIỀU HÀNH
[Tổng: X | Done: X | In Progress: X | Blocked: X]

### THEO THÀNH VIÊN
| Thành viên | Done | In Progress | Blocked | Ghi chú |
|------------|------|-------------|---------|---------|

### KHUYẾN NGHỊ
- Ngay lập tức (24–48h): ...
- Ngắn hạn (tuần này): ...

### RỦI RO & LƯU Ý
- Overdue: ...
- Blocked: ...

### ĐỘ TỰ TIN TỔNG THỂ
[Cao / Trung bình / Thấp]
```
