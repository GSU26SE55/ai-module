# Plan — GH-86: Uncertainty-aware health_stage & classification

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-05 | **Cập nhật lần cuối:** 2026-07-05
- **Issue:** #86 — https://github.com/GSU26SE55/ai-module/issues/86

## Mục tiêu

`health_stage` thỉnh thoảng ra sai khi SOH thật nằm gần ngưỡng cứng (80/85/90) — vì stage quyết định
bằng **point-estimate** (mean 10 MC samples) so với hard threshold, trong khi sai số model MAE ~1.98%
và soh_std ~1–2%. Case ghi nhận (GH-60): B0048 true SOH 82.9% → predicted 77.84% → "End Of Life"
(lệch 5.06 điểm, đúng phải là Maintenance Required).

Fix ở tầng inference bằng chính phân phối MC Dropout đã có — **không retrain, không thêm forward pass,
không ảnh hưởng latency 88.2ms**.

## Cơ sở khoa học (theo yêu cầu cite của ai.md)
- MC Dropout ≈ approximate Bayesian posterior → mỗi sample là 1 draw từ predictive distribution;
  dùng phân phối để ra quyết định thay vì chỉ mean — Gal & Ghahramani, ICML 2016.
- Probabilistic battery health diagnostics — Stanford Onori group (probability-of-exceedance trên
  ngưỡng EOL thay vì so sánh điểm).
- Median robust hơn mean với sample nhỏ (n=10) và phân phối lệch.
- Borderline/reject option khi max-class probability thấp — chuẩn reject-option classification;
  tinh thần deadband chống alarm chattering theo ISA-18.2.

## Scope

**Trong scope:**
1. `src/models/anomaly_detector.py` — thêm `classify_health_stage_probabilistic(mc_preds)`:
   - `soh_median` = median(mc_preds) (clip [0,100])
   - `stage_probabilities` = {"End Of Life": P(s<80), "Maintenance Required": P(80≤s<85),
     "Degrading": P(85≤s<90), "Healthy": P(s≥90)} — tính bằng đếm tỷ lệ samples
   - stage = argmax probability (tie-break về stage nặng hơn — an toàn cho maintenance)
   - `stage_confidence` = max probability; `is_borderline` = stage_confidence < 0.7
   - `classify_health_stage(soh)` cũ GIỮ NGUYÊN (fallback + backward compat cho callers khác)
2. `src/services/inference.py` — `run_inference()` gọi hàm mới với `mc_preds`;
   `prediction` block thêm `stage_probabilities`, `stage_confidence`, `is_borderline`;
   `health_stage` lấy từ kết quả probabilistic. `classification` (flat field cho BE)
   cũng chuyển sang dùng `soh_median` thay `soh` mean khi so ngưỡng — logic
   `classify_anomaly` không đổi, chỉ đổi input SOH sang median (2 field hiển thị
   `soh_percent` vẫn là mean như cũ để không đổi hành vi số liệu báo cáo).
3. `src/schemas/predict.py` — thêm 3 field optional vào response schema (backward compatible).
4. gRPC parity: `protos/ai_service.proto` thêm field number MỚI (không reuse số cũ),
   regen stub bằng `python scripts/gen_proto.py`, map trong `src/grpc_server.py`.
5. Tests: unit cho hàm mới (case biên 80/85/90, tie-break, borderline), reproduce case
   GH-60-like (mc_preds rải quanh 80 → is_borderline=true), parity REST/gRPC, giữ coverage ≥85%.

**Ngoài scope (không tự ý làm):**
- Giảm MAE model (GH-25 — Kaggle), tăng MC_RUNS (đánh đổi latency GH-63)
- Recalibrate ngưỡng IsolationForest −0.1/−0.3 (finding GH-70 — chờ GVHD)
- Hysteresis stateful theo previous_stage (cần BE gửi state — issue riêng nếu cần)
- Đổi `EOL_SOH`/`MAINTENANCE_SOH` (có cơ sở khoa học riêng, không đụng)

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/models/anomaly_detector.py` | modify | thêm `classify_health_stage_probabilistic()` |
| `src/services/inference.py` | modify | truyền `mc_preds`, thêm 3 field vào prediction block |
| `src/schemas/predict.py` | modify | 3 field optional mới trong response |
| `protos/ai_service.proto` | modify | field number mới (append-only) |
| `src/grpc_gen/*` | regen | `python scripts/gen_proto.py` |
| `src/grpc_server.py` | modify | map 3 field mới |
| `tests/test_models.py` | modify | unit tests hàm mới |
| `tests/test_inference.py` | modify | field mới trong response + case borderline |
| `tests/test_grpc_server.py` | modify | parity test |

## Approach — quyết định stage

```
mc_preds (10 samples, %) ──► đếm tỷ lệ rơi vào 4 bin [<80 | 80–85 | 85–90 | ≥90]
                              │
                              ├─ stage = bin có tỷ lệ cao nhất (tie → bin nặng hơn)
                              ├─ stage_confidence = tỷ lệ đó
                              └─ is_borderline = stage_confidence < 0.7
```

Ví dụ case GH-60: mc_preds ≈ [76.5 … 79.8] quanh 77.8, std ~1.1 → phần lớn samples < 80
→ stage vẫn "End Of Life" NHƯNG `stage_confidence` thấp hơn 1.0 và nếu samples vắt qua 80
→ `is_borderline=true` — BE/prescription biết đây là vùng xám thay vì tin tuyệt đối.
(Fix triệt để độ lệch 5 điểm là việc của GH-25 — plan này làm hệ thống trung thực về
uncertainty, không giả vờ chắc chắn.)

## Steps
- [x] Bước 1: `classify_health_stage_probabilistic()` + unit tests (case biên, tie-break) — 47 passed
- [x] Bước 2: wire vào `run_inference()` + schema REST → `pytest tests/test_inference.py tests/test_models.py` PASS
- [x] Bước 3: proto field mới (10–12) + regen + gRPC map → `pytest tests/test_grpc_server.py` parity PASS
- [x] Bước 4: full `pytest tests/ --cov=src` → 271 passed, coverage 89% ≥85%; benchmark `--real-weights` → Predict avg 95.0ms PASS
- [ ] Bước 5: `/kltn-reviewcode` → `/kltn-test 86`

## Kết quả verify trên real weights (2026-07-05)
- 16 windows B0048 true SOH=82.9% (case GH-60): lỗi chủ đạo là **bias hệ thống** của regression
  (pred 71–79, cả 10 MC samples < 80) — probabilistic staging không sửa được bias (đúng như scope),
  nhưng flag đúng `is_borderline=true` khi phân phối vắt qua ngưỡng (w7: conf=0.5).
- Val zone 83–87%: new staging đúng 10/32 vs old 9/32; 4/22 case sai được flag borderline.
- → Cải thiện chính là **trung thực về uncertainty** (BE/prescription biết vùng xám);
  giảm bias thuộc GH-25 (retrain Kaggle).
