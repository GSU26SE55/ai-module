## TEST REPORT — GH-56 — 2026-07-03
### Scope: AI
### Môi trường: local

### TÓM TẮT
Toàn bộ chức năng của GH-56 (readings API mở rộng 6-cột) hoạt động đúng, reproducible, backward-compatible với path 3/4-cột cũ, không crash ở boundary values. 1 test flaky không liên quan (`test_prescription.py`). **Phát hiện ngoài scope quan trọng:** dùng artifact thật `soh_mamba_v1.4.pth` (vừa train xong ngoài dự kiến) qua full `/predict` pipeline cho kết quả bất thường (`soh_percent=100%` cho cả pin khỏe lẫn pin degraded, `soh_confidence=0.0`) — xảy ra **giống hệt nhau ở cả 4-cột và 6-cột**, xác nhận đây là vấn đề của chính model/pipeline, không phải bug do GH-56 gây ra.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Schema validate 6-cột | readings 30×6 | accept | accept | ✅ PASS |
| Schema reject 5-cột | readings 30×5 | 422 | 422 | ✅ PASS |
| `_append_derived_features` 6-cột dùng trực tiếp | raw6 cycle_count=42, soc varying | col4=42/200, col5=soc/100 | khớp | ✅ PASS |
| Parity 6-cột vs 4-cột+cycle_idx | soc_percent BE khớp Coulomb counting | model input giống hệt | `np.allclose` pass | ✅ PASS |
| Parity REST vs gRPC (6-cột) | cùng payload | cùng readings đến `run_inference` | khớp bit-for-bit | ✅ PASS |
| Reproducibility `_append_derived_features` | cùng input 6-cột, chạy 2 lần | output giống hệt | `np.array_equal=True` | ✅ PASS |
| Latency 4-cột (baseline) | dummy model full-size d_model=64 | tham chiếu | avg 127.75ms (max 146.07ms) | ℹ️ Info (xem RỦI RO) |
| Latency 6-cột | dummy model full-size d_model=64 | ≈ baseline (không regression) | avg 132.41ms (max 158.90ms), chênh ~5ms | ✅ PASS (không regression) |
| `/health` endpoint | GET | status ok | `{"status":"ok",...}` | ✅ PASS |
| `/predict` 6-cột hợp lệ | JSON 30×6 | 200 | 200 | ✅ PASS |
| `/predict` 4-cột legacy | JSON 30×4 | 200 (hành vi không đổi) | 200 | ✅ PASS |
| `/predict` 5-cột (invalid) | JSON 30×5 | 422 | 422 | ✅ PASS |
| `/predict` 0-cột (invalid) | JSON 30×[] | 422 | 422 | ✅ PASS |
| Boundary: cycle_count=0 | pin mới hoàn toàn | 200, không crash | 200 | ✅ PASS |
| Boundary: cycle_count=5000 (OOD) | vượt CYCLE_COUNT_NORM=200 | 200, không crash (không validate range theo scope) | 200 | ✅ PASS |
| Boundary: soc_percent=0 | pin cạn hoàn toàn | 200, không crash | 200 | ✅ PASS |
| Boundary: cycle_count=-1 (invalid value) | giá trị âm | 200, không crash (không validate range theo scope) | 200 | ✅ PASS |

### Coverage
- Line coverage: **87%** (target ≥ 85%) — `src/schemas/predict.py` 100%, `src/services/inference.py` 94%

### Latency
- Avg inference (4-cột, dummy full-size model): 127.75ms
- Avg inference (6-cột, dummy full-size model): 132.41ms — chênh lệch ~4.7ms nằm trong noise, **không regression** so với path cũ
- Ghi chú: cả 2 số vượt 100ms SLA trên máy dev này vì MC Dropout (20 forward pass) trên CPU với `d_model=64` — pre-existing, không phải do GH-56. SLA chính thức benchmark qua `scripts/benchmark_grpc.py --real-weights` trên môi trường deploy, unit test dùng dummy `d_model=8` để nhanh/deterministic.

### Bugs tìm được
- Không có bug trong scope GH-56.

### RỦI RO & LƯU Ý
- 🔴 **[Ngoài scope GH-56 nhưng cần biết]** Model `soh_mamba_v1.4.pth` vừa được train thật (job nền hoàn thành ngoài dự kiến, xem `logs/GH-56/review.md`) đạt `test_mae=1.73%/test_rmse=2.06%` khi evaluate trong `train.py`, NHƯNG khi chạy qua full `/predict` pipeline với data thật (`demo/predict_degraded_6field.json`, true SOH=61.2%) lại trả `soh_percent=100%, classification=Normal, soh_confidence=0.0, soh_std=21.27`. Test cùng input qua path 4-cột legacy cho **kết quả giống hệt** → xác nhận đây là vấn đề của model/pipeline (có thể do MC Dropout variance quá lớn hoặc mismatch giữa `train.py` evaluate() và `run_inference()` full pipeline), **không phải bug do GH-56**. Cần điều tra riêng trước khi coi v1.4 là production-ready — không nên ship weight file này chung với GH-56.
- Test flaky `test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` khi chạy full suite (pass khi chạy riêng lẻ) — không liên quan `src/services/prescription.py` (GH-56 không đụng file này).
- File `models/weights/*.pkl/*.pth` và `notebooks/kaggle_train_long.ipynb` đang modified trong working tree nhưng ngoài scope GH-56 — không nên commit chung PR.

### KẾT LUẬN
PASS (cho scope GH-56) — Độ tự tin: Cao
