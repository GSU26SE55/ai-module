# GH-60 — Validation Report: v1.5 model qua full `/predict` pipeline

**Ngày:** 2026-07-03 | **Model:** `soh_mamba_v1.5.pth` (thật, train trên Kaggle sau GH-58+GH-59)

## 1. Health check

```json
{"status": "ok", "model_version": "1.5", "scaler_loaded": true, "mamba_loaded": true, "isolation_forest_loaded": true}
```

Load thành công — không còn `RuntimeError` (trước GH-58 fix, load bị lỗi do version mismatch).

## 2. Độ chính xác SOH — so với 4 demo payload (true SOH đã biết)

| Demo | True SOH | Predicted | Lệch (abs) | Classification | Confidence | soh_std |
|---|---|---|---|---|---|---|
| predict_healthy.json (B0048) | 82.9% | 77.84% | 5.06 | Failed | 0.776 | 1.122 |
| predict_degraded.json (B0048) | 61.2% | 62.79% | 1.59 | Failed | 0.794 | 1.030 |
| predict_degraded_6field.json (B0048) | 61.2% | 62.14% | 0.94 | Failed | 0.815 | 0.923 |
| predict_healthy_b0005.json (B0005) | 92.8% | 93.97% | 1.17 | Normal | 0.580 | 2.100 |

**MAE trên 4 mẫu: 2.19%** (target <2% — sát ngưỡng, cỡ mẫu quá nhỏ để kết luận thống kê chắc chắn, nhưng KHÔNG còn hiện tượng 100%/252% vô nghĩa như trước GH-58).

Checkpoint tự báo (từ `train.py`, trên `data/processed/test.pt` đầy đủ 768 window): `test_mae=1.9785%`, `test_rmse=2.3846%` — đáng tin cậy hơn vì cỡ mẫu lớn hơn nhiều so với 4 demo ở trên.

### Phát hiện: "Failed" cho pin healthy (B0048, true SOH=82.9%)
`classify_anomaly()` (`src/models/anomaly_detector.py`) dùng **SOH làm driver chính**, `EOL_SOH=80.0`: SOH<80→Failed. Model dự đoán 77.84% (lệch 5.06 điểm so với true 82.9%) — sai số nằm gần ngưỡng nhạy cảm 80%, khiến classification "flip" sang Failed dù bản thân sai số không quá lớn. **Không phải bug** — IsolationForest anomaly_score thực tế dương (0.18, "bình thường"), chính SOH regression là yếu tố quyết định flip. Đây là rủi ro cố hữu của bất kỳ ngưỡng cứng nào khi giá trị thật nằm sát biên — không sửa trong ticket này (ngoài scope, `EOL_SOH` có cơ sở khoa học riêng).

## 3. Latency benchmark (`scripts/benchmark_grpc.py --real-weights`)

```
RPC                             avg ms    p50 ms    p95 ms
----------------------------------------------------------
run_inference (direct)           454.7     453.6     562.3
Predict (unary)                  494.8     495.9     541.3
PredictStream (per window)       524.4     526.7     537.9
Prescribe (rule path)            479.5     490.4     575.1

Transport overhead (Predict avg - direct avg): 40.1ms
FAIL: Predict avg 494.8ms >= 100.0ms (P1 SLA)

RESULT: FAIL
```

**🔴 FAIL — vượt SLA ~5 lần** (494.8ms vs mục tiêu <100ms). Transport overhead (gRPC vs gọi trực tiếp) chỉ 40ms — phần lớn thời gian (~450ms) là tính toán thật: MC Dropout 20 forward pass trên model full-size (`d_model=64, d_state=16`) chạy CPU. Đây KHÁC với benchmark dummy trước đó trong phiên làm việc (127-132ms) — benchmark đó dùng model rất nhỏ (`d_model=8`) để test nhanh logic code, không phản ánh model thật.

**Lưu ý giới hạn:** benchmark chạy trên máy dev (CPU, không GPU) — theo `ai.md`, benchmark chính thức nên chạy trên môi trường deploy thật (có thể có GPU). Tuy nhiên mức vượt ngưỡng (~5x, không phải 1.2-1.5x) là đáng kể, khó chắc chắn GPU sẽ đủ để về dưới 100ms nếu không benchmark thử.

## 4. Kết luận

**KHÔNG PASS để ship production ngay** — Độ tự tin: Cao

| Tiêu chí (AC gốc GH-60) | Kết quả |
|---|---|
| Classification đúng cho pin degraded | ✅ Đạt (Failed, đúng) |
| SOH lệch trong khoảng chấp nhận | 🟡 Sát ngưỡng (MAE 2.19% trên mẫu nhỏ, 1.98% theo báo cáo train.py cỡ mẫu lớn) |
| Latency <100ms | 🔴 **FAIL rõ ràng** — 494.8ms, vượt ~5x |
| Kết luận rõ ràng | ✅ Có — xem bên dưới |

**Khuyến nghị bước tiếp theo (cần quyết định, không tự ý làm trong ticket này):**
1. Benchmark lại trên môi trường deploy thật (có GPU) trước khi kết luận cuối — nếu GPU đưa về <100ms thì latency không còn là blocker
2. Nếu môi trường deploy cũng chỉ có CPU: cân nhắc giảm `MC_RUNS` (hiện 20 forward pass) — đánh đổi giữa tốc độ và độ chính xác của `soh_confidence`/`soh_std`, cần bàn với leader/team vì đây là thay đổi ảnh hưởng thiết kế uncertainty quantification, ngoài scope 1 ticket validation
3. MAE sát ngưỡng 2% — nên theo dõi thêm khi có nhiều dữ liệu thật hơn, không cần hành động ngay
