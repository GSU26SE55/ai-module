# Plan — GH-62: Optimize MC Dropout inference latency — batch 20 forward passes into 1

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-04
- **Issue:** #62 — https://github.com/GSU26SE55/ai-module/issues/62
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
GH-60 benchmark thật (`--real-weights`) cho `Predict avg 494.8ms >= 100ms SLA` — FAIL rõ ràng. Đã profile ra nguyên nhân: MC Dropout hiện lặp 20 lần gọi model tuần tự (`for _ in range(MC_RUNS): model(...)`), chiếm >99% latency. Đã đo thử: gộp thành 1 lần gọi batch (`x_tensor.repeat(20,1,1)`) cho cùng kết quả thống kê nhưng nhanh hơn 2.5x (295ms → 120ms). Output: `run_inference()` dùng batched MC Dropout, giảm latency đáng kể, không đổi ý nghĩa thống kê của `soh_percent`/`soh_confidence`/`soh_std`.

## Scope
**Trong scope:**
- Sửa `run_inference()` (`src/services/inference.py`) — thay vòng lặp 20 lần gọi model đơn lẻ bằng 1 lần gọi model với batch=`MC_RUNS`
- Verify kết quả (`soh_percent`, `soh_std`, `soh_confidence`) tương đương ý nghĩa thống kê so với trước (cùng random dropout, chỉ khác cách gọi — không phải cùng giá trị bit-for-bit vì dropout mask vẫn ngẫu nhiên mỗi lần chạy, nhưng phân phối kết quả phải giống)
- Đo lại latency bằng `scripts/benchmark_grpc.py --real-weights`, so với baseline 494.8ms

**Ngoài scope:**
- Không đổi `MC_RUNS=20` (giữ nguyên số lượng sample, không đánh đổi chất lượng confidence) — nếu sau khi batch vẫn >100ms, đó là quyết định riêng cần bàn thêm (đã ghi rõ trong issue), không tự ý làm trong ticket này
- Không đổi kiến trúc model, không retrain
- Không tối ưu phần khác của pipeline (scaling/feature extraction/isolation forest) — các bước này đã đo chỉ ~3ms tổng, không đáng kể
- Không benchmark trên môi trường deploy GPU thật (chỉ local CPU, giống GH-60)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/inference.py` | modify | `run_inference()`: batch MC Dropout — `x_tensor.repeat(MC_RUNS,1,1)`, `x_feat_tensor.repeat(MC_RUNS,1)`, 1 lần gọi `model(xb, xfb)` thay vì vòng lặp |
| `tests/test_inference.py` | modify | Test xác nhận vẫn ra đúng shape/range kết quả sau khi đổi cách gọi; đo latency nhanh hơn rõ rệt so với trước (không cần threshold cứng, chỉ so sánh tương đối hoặc log) |

## Approach
- Thay:
  ```python
  mc_preds = [model_loader.soh_model(x_tensor, x_feat_tensor).item() * 100 for _ in range(MC_RUNS)]
  ```
  bằng:
  ```python
  xb = x_tensor.repeat(MC_RUNS, 1, 1)
  xfb = x_feat_tensor.repeat(MC_RUNS, 1)
  mc_preds = (model_loader.soh_model(xb, xfb) * 100).tolist()
  ```
- Giữ nguyên `_MC_LOCK`, `model.train()`/`model.eval()` try/finally, và toàn bộ logic tính `soh`/`soh_std`/`soh_confidence` phía sau (không đổi công thức, chỉ đổi cách sinh `mc_preds`)
- `MambaSOHPredictor.forward()` đã generic theo batch dimension `(B, L, d_model)` (xác nhận qua code + train.py dùng batch=32) — không cần sửa model

## Edge Cases
- Batch=20 tăng peak memory so với batch=1×20 lần — không đáng kể với model nhỏ (`d_model=64`), không cần xử lý riêng
- Nếu `torch.compile` (CUDA, `reduce-overhead`) đã compile với shape batch=1 từ trước đó trong cùng process → đổi sang batch=20 cố định và nhất quán mỗi lần gọi, không phải shape thay đổi liên tục nên không có vấn đề re-compile động

## Acceptance Criteria
- [ ] MC Dropout dùng 1 lần gọi model (batched, shape `(MC_RUNS, ...)`) thay vì vòng lặp 20 lần
- [ ] `pytest tests/test_inference.py` pass, không regression (shape, range, warnings vẫn đúng)
- [ ] Latency `scripts/benchmark_grpc.py --real-weights` cải thiện rõ rệt so với baseline 494.8ms (ghi số liệu thật, không cần đạt <100ms tuyệt đối nếu môi trường local CPU không đủ — nhưng phải cải thiện đáng kể, tham chiếu benchmark thử đã đo ~120-160ms)
- [ ] `soh_percent`/`soh_confidence` cho cùng 4 demo payload (GH-60) không lệch nhiều so với kết quả GH-60 đã ghi nhận (cùng model, chỉ khác cách gọi — sai số chấp nhận trong khoảng ngẫu nhiên MC dropout tự nhiên)

## Steps
- [x] Bước 1 (Inference): sửa `run_inference()` trong `src/services/inference.py` — batch MC Dropout — 2026-07-04
- [x] Bước 2 (Unit test): 2 test mới trong `tests/test_inference.py` (stochastic vẫn giữ, batched nhanh hơn sequential) — 2026-07-04
- [x] Bước 3: full suite 205 passed (0 fail, kể cả flaky trước đó), coverage 87%, ruff chỉ pre-existing — 2026-07-04
- [x] Bước 4: benchmark lại — **494.8ms → 119.3ms (4.15x nhanh hơn)**, vẫn FAIL nhưng chỉ vượt ~19% (trước ~5x) — `logs/GH-62/benchmark_result.md` — 2026-07-04
- [x] Bước 5: 4 demo payload MAE 2.127% (trước 2.19%, chênh trong dao động MC Dropout tự nhiên) — không regression — 2026-07-04

## Câu hỏi đã giải đáp
- Không cần hỏi thêm — approach đã được validate bằng số liệu đo thật trong lúc viết issue (295ms→120ms), kiến trúc model đã xác nhận hỗ trợ batch dimension sẵn, không có test nào phụ thuộc cách gọi tuần tự.
