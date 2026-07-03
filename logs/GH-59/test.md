## TEST REPORT — GH-59 — 2026-07-03
### Scope: AI
### Môi trường: local

### TÓM TẮT
Clip `cycle_count_norm` về `[0,1]` + log warning hoạt động đúng trên cả unit test lẫn full REST endpoint (end-to-end qua `/predict`, không mock `_append_derived_features`). Không crash ở bất kỳ giá trị boundary nào, reproducible, không regression.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| `cycle_idx=5000` (path derive server-side) | `_append_derived_features(..., cycle_idx=5000)` | `cycle_count_norm=1.0`, log warning chứa "cycle_count=5000" | khớp | ✅ PASS |
| `cycle_idx=-1` (âm) | `_append_derived_features(..., cycle_idx=-1)` | `cycle_count_norm=0.0`, không crash | khớp | ✅ PASS |
| `cycle_idx=200` (đúng biên) | `_append_derived_features(..., cycle_idx=200)` | `cycle_count_norm=1.0`, KHÔNG log warning | khớp (`caplog.text==""`) | ✅ PASS |
| Path 6-cột (BE gửi `cycle_count=5000` trực tiếp) | `raw6` với cột 5=5000.0 | clip 1.0, log warning | khớp | ✅ PASS |
| `preprocess.py` — `cycle_idx=5000` | `cycles_to_windows([(cycle, 95.0, 5000)], scaler)` | `X[:,:,4]=1.0` toàn bộ | khớp | ✅ PASS |
| `preprocess.py` — `cycle_idx=50` (trong range) | `cycles_to_windows([(cycle, 95.0, 50)], scaler)` | `X[:,:,4]=50/200=0.25`, không đổi | khớp | ✅ PASS |
| Reproducibility | cùng input, `_append_derived_features` chạy 2 lần với `cycle_idx=350` | output giống hệt | `np.array_equal=True` | ✅ PASS |
| Log message thật (console) | `cycle_idx=350` qua real logger (không mock) | `WARNING:src.services.inference:cycle_count=350 outside expected range [0, 200.0] — clipping...` | in ra đúng, rõ ràng | ✅ PASS |
| **End-to-end `/predict`** — boundary sweep | `cycle_count` ∈ {0, 200, 350, 5000, -1} qua REST thật (`TestClient`, không mock `_append_derived_features`) | tất cả 200, warning chỉ log cho 350/5000/-1, không log cho 0/200 | khớp chính xác | ✅ PASS |
| Full suite | `pytest tests/ --cov=src` | ≥85% coverage, pass | 202 passed / 1 flaky (không liên quan) | ✅ PASS |

### Coverage
- Line coverage: **87%** (target ≥ 85%) — `src/services/inference.py` 95%

### Bugs tìm được
- Không có bug mới.

### RỦI RO & LƯU Ý
- Test flaky `test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` khi chạy full suite — không liên quan `prescription.py`, đã xác nhận nhiều lần ở các ticket trước.
- Fix này là no-op cho model hiện tại (chưa retrain) — giá trị thực sự phát huy tác dụng từ lần train Kaggle tiếp theo (gộp chung GH-58, đã lưu ý ở review).
- 1 điểm nhỏ đã ghi ở review: log warning trigger cả 2 chiều (âm + vượt trên), rộng hơn mô tả gốc trong issue — đã cập nhật `plan.md` cho khớp, không phải bug.

### KẾT LUẬN
PASS — Độ tự tin: Cao
