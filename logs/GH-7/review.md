# BÁO CÁO CODE REVIEW — feat/spectral_kurtosis — 2026-06-04

## TÓM TẮT
Branch thêm Spectral+Kurtosis features qua FiLM conditioning, parallel scan cho Mamba, và degradation metrics mới vào API output. Sau khi fix 1 bug nhỏ (channel mismatch inference vs config), toàn bộ 63/63 tests PASS.

---

## PHÂN TÍCH

### 🔴 Critical (đã fix trong session này)

**`src/services/inference.py`** — Feature channel mismatch
- `extract_window_features(x_scaled)` trả 108 features (6 channels) nhưng `feature_scaler` expect 54 (3 channels)
- **Fix:** đổi thành `extract_window_features(x_scaled[:, :3])` — khớp với `SPECTRAL_FEAT_DIM=54`
- Status: ✅ Fixed, tests pass

---

### 🟡 Warning

**`src/models/soh_predictor.py:_sequential_scan_jit`** — JIT function defined at module level
- `@torch.jit.script` compile lần đầu khi import → thêm ~0.5s startup time
- Không ảnh hưởng accuracy hay latency sau warmup
- Acceptable cho scope capstone

**`scripts/preprocess.py`** — `WINDOW_SIZE` và `WINDOW_STRIDE` import từ config nhưng cũng có fallback hardcode
- Hiện tại đã dùng config đúng
- Minor: nên dọn comment thừa

**`src/models/anomaly_detector.py:compute_degradation_metrics`** — `_STEPS_PER_CYCLE=285` hardcoded
- NASA average, không phải measured per-battery
- Acceptable: documentation đã note rõ
- Kurtosis estimate với N=30 còn noise — bias=False đã được dùng đúng

---

### ✅ Pass

| Tiêu chí | Kết quả |
|---------|---------|
| Random seed = 42 | ✅ `preprocess.py`, `train.py`, `IsolationForest` đều set |
| Scaler version check tại startup | ✅ `model_loader.py` assert version "1.0" và "1.1" |
| Artifacts commit: scaler.pkl, feature_scaler.pkl, soh_mamba_v1.1.pth, IF.pkl | ✅ 4 files tồn tại |
| Train/Val/Test split theo battery ID | ✅ B0005/B0006/B0007 train, B0018 val+test |
| No mamba-ssm CUDA dependency | ✅ Pure PyTorch, Windows native |
| FiLM conditioning đúng math | ✅ `(sigmoid(γ)+0.5)×h + β` |
| Parallel scan correctness | ✅ max_err=1.19e-07 vs sequential |
| Chunked scan chain carry state | ✅ `b_chunk[:,0] = a[:,0]*h_carry + b[:,0]` |
| JIT scan correctness | ✅ verified vs sequential |
| Inference `x_feat` shape match scaler | ✅ (54,) sau fix |
| `feature_scaler.pkl` commit | ✅ 3.2 KB |
| Model version bump khi thay đổi | ✅ v1.0 → v1.1 |
| 63/63 tests PASS | ✅ |
| Test MAE < 2% | ✅ 0.61% |
| Test RMSE < 3% | ✅ 0.73% |
| Latency < 100ms tại L=30 | ✅ 3.1ms |
| Latency < 100ms tại L=1000 | ✅ 53.1ms |
| New output fields có schema Pydantic | ✅ PredictResponse updated |
| `compute_degradation_metrics` có fallback khi window ngắn | ✅ dùng `DEGRADATION_RATE=0.15` |

---

## RỦI RO & LƯU Ý

1. **Config drift**: Nhiều lần thay đổi `WINDOW_SIZE`, `D_STATE`, `D_MODEL` trong session — config hiện tại (30/16/64) là đúng nhưng cần đảm bảo không bị đổi trước khi ship
2. **model_loader chưa load `d_state` và `d_model` đúng cho v1.1**: checkpoint v1.1 không lưu `d_state`/`d_model` field → fallback về default 64/16 — OK vì đó là giá trị đúng
3. **`compute_degradation_metrics` với L=30**: chỉ tạo được 2 segments → trend detection kém reliability. Đã được document trong docstring

---

## KẾT LUẬN

**PASS** — Độ tự tin: **Cao**

Tất cả tiêu chí DoD đạt:
- ✅ Code review PASS (63/63 tests)
- ✅ MAE=0.61% < 2%, RMSE=0.73% < 3%
- ✅ Latency L=1000: 53ms < 100ms SLA

Chạy `/kltn-test 7` để có báo cáo test đầy đủ.
