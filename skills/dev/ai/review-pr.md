# Skill: /kltn-reviewpr (AI)

## Kích hoạt
`/kltn-reviewpr KAN-XX` — review PR của đồng đội phía AI/ML module trước khi approve merge.

---

## Quy trình

1. **Đọc PR** — lấy diff và PR description
   ```bash
   gh pr view <số PR hoặc KAN-XX> --json title,body,files
   gh pr diff <số PR hoặc KAN-XX>
   ```

2. **Kiểm tra PR description** trước khi đọc code:
   - [ ] Có ticket ID (KAN-XX)?
   - [ ] Có kết quả metric (MAE, RMSE, F1) trong description?
   - [ ] Checklist reproducible đã được tích?

3. **Chạy checklist code** (góc nhìn outsider — không phải tác giả)

---

## Checklist

### Reproducibility
- [ ] `random_seed` được set ở đầu script?
- [ ] Phiên bản thư viện được pin trong `requirements.txt`?
- [ ] Kết quả metric trong PR description khớp khi chạy lại?

### Data
- [ ] Train / Validation / Test split rõ ràng, không lẫn lộn?
- [ ] Không có data leakage tiềm ẩn (test set ảnh hưởng training)?
- [ ] Preprocessing nhất quán giữa train và inference?

### Model
- [ ] Vẫn chỉ 2 core model (LSTM/CNN-LSTM + 1 anomaly detection), không tự thêm?
- [ ] Metric đánh giá rõ ràng (MAE/RMSE cho SOH, F1 cho classification)?
- [ ] Không claim accuracy > 95% mà không có justification?

### FastAPI Endpoint
- [ ] Input/output schema được define bằng Pydantic?
- [ ] Model load 1 lần lúc startup, không load mỗi request?
- [ ] Xử lý lỗi khi input không hợp lệ?

### Artifacts
- [ ] Không commit model weights lớn (`.pt`, `.pth` > 50MB) vào Git?
- [ ] Không commit raw dataset?

### Conflict
- [ ] Branch không có conflict với `main`?

---

## Output
```
## BÁO CÁO PR REVIEW — KAN-XX — [YYYY-MM-DD]
### Reviewer: [tên bạn]
### TÓM TẮT
[1–2 câu về PR]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### KHUYẾN NGHỊ
- Ngay lập tức: ...

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[APPROVE / REQUEST CHANGES] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Nếu REQUEST CHANGES → comment rõ trên PR, không approve.
