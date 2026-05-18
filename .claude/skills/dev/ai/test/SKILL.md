# Skill: /kltn-test (AI)

## Kích hoạt
`/kltn-test GH-[number]` — chạy test AI module sau khi `/kltn-reviewcode` PASS.

---

## ACTION-FIRST RULE

**Chạy lệnh test thực sự TRƯỚC khi viết báo cáo.** Không đoán kết quả từ việc đọc code. Không bao giờ claim "PASS" khi chưa chạy lệnh. Tool calls trước, text output sau.

---

## Effort Scaling

| Level | Khi nào | Làm gì |
|-------|---------|--------|
| **Quick** | 1 function đơn giản | Chạy test + kiểm tra reproducibility |
| **Standard** | 1 ticket / 1 feature | pytest + coverage + latency benchmark |
| **Deep** | PR train + inference + API | Full: pytest + endpoint test + benchmark |
| **Exhaustive** | Cuối sprint / trước demo | Full + metric evaluation + regression test |

---

## Bước 1 — Xác định ticket

Issue number lấy từ argument của lệnh. Nếu không có:
```bash
git branch --show-current | grep -oE 'GH-[0-9]+'
# feature/GH-56-soh-lstm → GH-56
```

---

## Bước 2 — Chuẩn bị môi trường

- Không test production — chỉ test local
- Dùng sample từ NASA dataset (không dùng full dataset)
- Model weights và `scaler.pkl` phải có ở `models/weights/`

---

## Bước 3 — Chạy pytest với coverage

```bash
pytest tests/ -v --cov=api --cov=data --cov=models --cov=train --cov-report=term-missing
```

Target: **≥ 85% line coverage**. CI fail nếu < 85%.

---

## Bước 4 — Kiểm tra reproducibility

```bash
# Chạy 2 lần với cùng input — kết quả phải giống nhau
python -c "from models.soh_predictor import SOHPredictor; import torch; m=SOHPredictor(); m.eval(); x=torch.rand(1,30,3); print(m(x).item())"
python -c "from models.soh_predictor import SOHPredictor; import torch; m=SOHPredictor(); m.eval(); x=torch.rand(1,30,3); print(m(x).item())"
# Phải ra cùng output → seed = 42 hoạt động đúng
```

---

## Bước 5 — Latency benchmark

```bash
pytest tests/test_inference.py -v -s
# Expected: Avg inference latency: X ms ✅ (phải < 100ms — P1 SLA = 4h)
```

---

## Bước 6 — Test FastAPI endpoint

```bash
# Khởi động server
uvicorn src.main:app --port 8001 &

# Health check
curl -s http://localhost:8001/health
# Expected: {"status":"ok","scaler_loaded":true,"lstm_loaded":true,...}

# Predict endpoint
curl -s -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"voltage": [...], "current": [...], "temperature": [...]}'
# Expected: {"status":"Normal|Degrading|Failed","soh_percent":X,"confidence":Y}
```

---

## Bước 7 — Checklist test bắt buộc

- [ ] Unit test cho `preprocess` — đầu vào/ra đúng shape (batch, 30, 3), seed=42
- [ ] Unit test cho `train` — loss giảm sau N epoch (smoke test, không cần full train)
- [ ] Unit test cho `infer` — cùng input → cùng output (reproducibility)
- [ ] Latency benchmark — inference < 100ms
- [ ] Input validation — endpoint nhận đúng schema Pydantic, reject sai schema
- [ ] Output format — response có đủ: `status`, `soh_percent`, `confidence`
- [ ] Boundary values — SOH = 0%, 100%, âm → xử lý đúng (không crash)
- [ ] Startup load — model load 1 lần, không load mỗi request

Nếu thiếu test case → báo FAIL, yêu cầu dev bổ sung trước khi ship.

---

## Adversarial Self-Review

Trước khi nộp báo cáo:

1. **Test case có thực sự chạy không?** — Không claim PASS nếu không có output pytest
2. **Reproducibility đã verify chưa?** — Chạy inference 2 lần, so sánh kết quả thực tế
3. **Latency có đo được không?** — Con số cụ thể (ms), không phải "có vẻ nhanh"
4. **Endpoint test có chạy thực sự không?** — curl output, không đọc code
5. **Coverage có đủ 85% không?** — In ra số thực tế từ pytest output

---

## Định dạng báo cáo

Sau khi chạy test xong, **bắt buộc ghi file** (dùng Write tool):

```
logs/GH-[number]/test.md
```

Nếu folder chưa tồn tại → tạo mới. Nội dung file:

```markdown
## TEST REPORT — GH-[number] — [YYYY-MM-DD]
### Scope: AI
### Môi trường: local

### TÓM TẮT
[1–2 câu về kết quả tổng thể]

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| preprocess shape | sample_input | (1, 30, 3) | (1, 30, 3) | ✅ PASS |
| reproducibility | same_input x2 | same_output | same_output | ✅ PASS |
| inference latency | sample_input | < 100ms | 42ms | ✅ PASS |
| /health endpoint | GET | status ok | status ok | ✅ PASS |
| /predict valid input | valid JSON | status+soh+conf | 200 OK | ✅ PASS |
| /predict invalid schema | missing fields | 422 | 422 | ✅ PASS |

### Coverage
- Line coverage: X% (target ≥ 85%)

### Latency
- Avg inference: X ms (target < 100ms)

### Bugs tìm được
- 🔴 [Critical] Inference cho kết quả khác nhau cùng input
  - Steps: chạy `predict(sample)` 2 lần → kết quả khác nhau
  - Cause: `random_seed` không được set trong inference script
  - Fix: thêm `torch.manual_seed(42)` đầu `infer.py`

### RỦI RO & LƯU Ý
- ...

### KẾT LUẬN
[PASS / FAIL] — Độ tự tin: [Cao / Trung bình / Thấp]
```

---

## Common Anti-Patterns

### Claim PASS mà không chạy test thực sự

**SAI:**
```
Đọc train.py → "seed=42 có đó" → Báo cáo: ✅ PASS reproducibility
```
_Vấn đề:_ seed có thể bị override trong thư viện khác, hoặc chỉ set một chỗ nhưng thiếu chỗ khác.

**ĐÚNG** — Verify thực sự:
```bash
python -c "from src.infer import predict; print(predict(sample))"
# Run 1: soh=82.3, status=Normal
python -c "from src.infer import predict; print(predict(sample))"
# Run 2: soh=82.3, status=Normal ✅ reproducible
```

---

### Không test boundary values

**SAI:**
```
| /predict valid input | 200 OK | 200 OK | ✅ PASS |
KẾT LUẬN: PASS
```

**ĐÚNG** — Test edge cases:
```
| /predict valid input      | 200+soh=82  | 200+soh=82   | ✅ PASS |
| /predict missing voltage  | 422         | 422           | ✅ PASS |
| /predict SOH boundary 0%  | clamped=0   | -2.3% (!)     | ❌ FAIL |
| /predict SOH boundary 100%| clamped=100 | 103.1% (!)    | ❌ FAIL |
```
