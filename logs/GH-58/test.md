## TEST REPORT — GH-58 — 2026-07-03
### Scope: AI
### Môi trường: local

### TÓM TẮT
Fix spectral-feature train/serve mismatch hoạt động đúng, reproducible, không regression trên toàn bộ suite. Version bump (Critical tìm được ở code review) đã verify hoạt động đúng thiết kế: app từ chối khởi động với message rõ ràng khi thiếu artifact v1.5, thay vì âm thầm dùng weight cũ sai.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| `cycles_to_windows` — 2 window khác nhau trong 1 cycle | cycle 90 timestep, 3 pattern tín hiệu khác nhau (sine/ramp/flat) | `X_feat` 3 dòng khác nhau | khác nhau (`not np.allclose` pass cả 3 cặp) | ✅ PASS |
| `cycles_to_windows` khớp `run_inference()` | 1 cycle đúng 30 timestep | `X_feat[0]` == `extract_window_features(x_scaled[:,:3])` | khớp `np.testing.assert_allclose` | ✅ PASS |
| Reproducibility | cùng cycle, chạy `cycles_to_windows` 2 lần | X, X_feat, y giống hệt | `np.array_equal = True` cho cả 3 | ✅ PASS |
| `test_windows_have_six_columns` / `test_soc_recomputed_per_window` (GH-54, regression check) | — | không đổi hành vi | pass | ✅ PASS |
| Edge case: cycle ngắn hơn WINDOW_SIZE (15 < 30) | cycle 15 timestep | 0 window, không crash | `X.shape=(0,)`, không exception | ✅ PASS |
| Version bump — fail loudly khi thiếu artifact | `model_loader.load_models()` (real, không mock) | `RuntimeError` rõ ràng, không load nhầm weight cũ | `RuntimeError: [STARTUP] Mamba model artifact not found at '...soh_mamba_v1.5.pth'` | ✅ PASS (đúng thiết kế) |
| Full suite | `pytest tests/ --cov=src` | ≥85% coverage, pass | 196 passed / 1 flaky (không liên quan) | ✅ PASS |

### Coverage
- Line coverage: **87%** (target ≥ 85%) — `scripts/preprocess.py` không tính trong `--cov=src` (nằm ngoài `src/`) nhưng được cover gián tiếp qua `tests/test_preprocess.py` (17/17 pass)

### Bugs tìm được
- Không có bug mới. 1 Critical đã tìm và sửa ở bước code review (`/kltn-reviewcode`) — đã verify lại ở đây (fail-loudly hoạt động đúng).

### RỦI RO & LƯU Ý
- Sau version bump, **local app sẽ không khởi động được** (thiếu `soh_mamba_v1.5.pth`/`isolation_forest_v1.5.pkl`) cho tới khi retrain trên Kaggle — đây là hành vi có chủ đích, không phải bug, nhưng cần biết trước khi pull/deploy.
- Test flaky `test_prescription.py::TestPrescriptionLatency::test_rule_path_under_100ms` khi chạy full suite (đã xác nhận nhiều lần không liên quan tới thay đổi của ticket này).
- `scripts/preprocess.py` không nằm trong phạm vi `--cov=src` (chỉ cover code trong `src/`) — coverage số liệu 87% không phản ánh trực tiếp % dòng của chính file đã sửa; độ tin cậy dựa vào 17/17 test pass trong `test_preprocess.py` thay vì % dòng.

### KẾT LUẬN
PASS — Độ tự tin: Cao
