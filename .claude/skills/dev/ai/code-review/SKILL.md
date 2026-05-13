# Skill: /kltn-reviewcode (AI)

## Kích hoạt
`/kltn-reviewcode` — review code AI/ML trước khi ship.

---

## ACTION-FIRST RULE

**Đọc diff thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
git diff main...HEAD
# hoặc nếu đã stage: git diff --staged
```

Không nhận xét từ memory. Tool calls trước, text output sau.

---

## Effort Scaling

| Level | Khi nào | Làm gì |
|-------|---------|--------|
| **Quick** | 1 script nhỏ, ít thay đổi | Chỉ check Critical: seed, scaler, data leakage |
| **Standard** | 1 ticket / 1 feature | Full checklist, phân tích từng vấn đề |
| **Deep** | PR train + inference + API | Full checklist + architecture consistency |
| **Exhaustive** | Cuối sprint / model retrain | Full + metric review + latency benchmark |

---

## Xác định issue number

```bash
git branch --show-current | grep -oE 'GH-[0-9]+'
# feature/GH-56-soh-lstm-model → TICKET_ID = GH-56
```

Nếu không xác định được → hỏi user trước khi tiếp tục.

---

## Checklist

### Reproducibility
- [ ] `random_seed = 42` được set ở đầu mọi script (train, preprocess)?
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
- [ ] Model được load 1 lần khi startup (`lifespan`), không load mỗi request?
- [ ] `scaler.pkl` được load cùng model khi startup?
- [ ] CORS middleware được cấu hình để BE gọi được?

---

## Adversarial Self-Review

Trước khi nộp báo cáo:

1. **Đã đọc diff chưa?** — Không nhận xét từ memory
2. **Random seed đã check chưa?** — Thiếu seed là Critical, không Warning
3. **Data leakage có thực sự kiểm tra chưa?** — Đọc code split, không đoán
4. **Scaler workflow đúng không?** — fit train → save pkl → load khi inference
5. **Kết luận PASS/FAIL nhất quán không?** — Có Critical → phải FAIL

---

## Định dạng báo cáo

Sau khi review xong, **bắt buộc ghi file** (dùng Write tool):

```
logs/GH-[number]/review.md
```
(TICKET_ID đã xác định ở trên, ví dụ: `logs/GH-56/review.md`)

Nếu folder chưa tồn tại → tạo mới. Nội dung file:

```markdown
## BÁO CÁO CODE REVIEW — [branch] — [YYYY-MM-DD]
### Scope: AI
### Effort: [Quick / Standard / Deep / Exhaustive]

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

---

## Common Anti-Patterns

### Bỏ qua random seed vì "kết quả trông ổn"

**SAI:**
```
Chạy train.py → loss giảm → ✅ Pass: model train bình thường
KẾT LUẬN: PASS
```
_Vấn đề:_ Thiếu seed → kết quả không reproducible → không thể so sánh metric giữa các run.

**ĐÚNG** — Kiểm tra seed trong diff:
```bash
grep -n "random_seed\|torch.manual_seed\|np.random.seed\|random.seed" train.py
# Không thấy → 🔴 Critical: train.py — thiếu random seed
# Fix: thêm random_seed = 42 đầu script + torch.manual_seed(42)
```

---

### Không kiểm tra scaler workflow

**SAI:**
```
✅ Pass: model architecture đúng
✅ Pass: FastAPI endpoint có Pydantic schema
KẾT LUẬN: PASS
```

**ĐÚNG** — Kiểm tra end-to-end scaler flow:
```bash
git diff main...HEAD | grep -n "scaler\|MinMaxScaler\|fit\|transform"
# inference.py:15: scaler = MinMaxScaler(); scaler.fit(X_inference)  ← fit lại trên production!
# 🔴 Critical: inference.py:15 — scaler được fit lại trên production data
#    Fix: load scaler từ models/weights/scaler.pkl thay vì fit lại
```
