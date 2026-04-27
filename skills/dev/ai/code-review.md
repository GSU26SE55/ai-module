# Skill: /kltn-reviewcode (AI)

## Kích hoạt
`/kltn-reviewcode` — review code AI/ML trước khi ship.

---

## Checklist

### Reproducibility
- [ ] `random_seed` được set ở đầu script?
- [ ] Phiên bản thư viện được pin trong `requirements.txt`?
- [ ] Có thể chạy lại và ra kết quả tương tự không?

### Data
- [ ] Train / Validation / Test split rõ ràng, không lẫn lộn?
- [ ] Không có data leakage (test set không ảnh hưởng training)?
- [ ] Data preprocessing nhất quán giữa train và inference?

### Model
- [ ] Chỉ 2 core model: LSTM/CNN-LSTM + 1 anomaly detection?
- [ ] Metric đánh giá rõ ràng (MAE, RMSE cho SOH; F1 cho classification)?
- [ ] Không claim accuracy > 95% mà không có justification?

### FastAPI Endpoint
- [ ] Input/output schema được define bằng Pydantic?
- [ ] Xử lý lỗi khi input không hợp lệ?
- [ ] Model được load 1 lần khi startup, không load mỗi request?

---

## Output
```
## BÁO CÁO CODE REVIEW — [branch]
### TÓM TẮT
[1–2 câu về trạng thái tổng thể]

### PHÂN TÍCH
🔴 Critical: [file:line] — vấn đề — cách fix
🟡 Warning:  [file:line] — vấn đề — gợi ý
✅ Pass: [tiêu chí đạt]

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

Sau khi có kết quả, lưu vào:
```
logs/KAN-XX/review.md
```
Nếu folder chưa tồn tại → tạo mới.
