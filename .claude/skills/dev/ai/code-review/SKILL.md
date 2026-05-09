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
- [ ] `MinMaxScaler` chỉ `.fit()` trên train set — không fit lại trên val/test?
- [ ] `scaler.pkl` được lưu tại `models/weights/scaler.pkl` sau khi train?
- [ ] Inference dùng scaler đã lưu — không tạo scaler mới?

### Model
- [ ] Chỉ 2 core model: LSTM/CNN-LSTM + 1 anomaly detection?
- [ ] Metric đánh giá rõ ràng: MAE < 2% / RMSE < 3% cho SOH; F1 > 0.80 cho classification?
- [ ] Không claim accuracy > 95% mà không có justification?
- [ ] Input window size đúng 30 timesteps? Input features đúng 3 (voltage, current, temperature)?

### FastAPI Endpoint
- [ ] Input/output schema được define bằng Pydantic?
- [ ] `get_model` dependency lấy từ `request.app.state.model`, không tự load?
- [ ] Xử lý lỗi khi input không hợp lệ?
- [ ] Model được load 1 lần khi startup, không load mỗi request?
- [ ] `scaler.pkl` được load cùng model khi startup (trong `lifespan`)?
- [ ] CORS middleware được cấu hình để BE gọi được?

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
