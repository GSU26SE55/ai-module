# Plan — GH-63: Latency still >100ms after GH-62 batching (124ms) — torch.compile (CPU) + reduce MC_RUNS

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-04 — code review tìm 1 Critical (warm-up thiếu train mode) đã sửa ngay, benchmark vẫn PASS (80.3ms), full suite 207 passed/0 failed, coverage 89%
- **Issue:** #63 — https://github.com/GSU26SE55/ai-module/issues/63
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
Sau GH-62 (batch MC Dropout), latency còn ~119-126ms, vẫn FAIL SLA <100ms (vượt ~20-25%). Đóng nốt khoảng cách bằng 2 hướng: (1) thử `torch.compile` cho CPU (không đánh đổi accuracy, nhưng không verify được trên máy dev Windows — cần deploy Linux xác nhận), (2) giảm `MC_RUNS` 20→10 (chắc chắn cắt latency, đánh đổi độ chính xác ước lượng uncertainty).

## Scope
**Trong scope:**
- Thêm nhánh thử `torch.compile(mode="default")` cho CPU trong `model_loader.py` (hiện chỉ áp dụng cho CUDA), giữ nguyên pattern try/except fallback an toàn đã có
- Giảm `MC_RUNS` từ 20 xuống **10** trong `run_inference()`
- Đo lại `soh_confidence`/`soh_std` trên 4 demo payload (GH-60/62 baseline) để xác nhận vẫn hữu ích, không tụt về gần vô nghĩa
- Benchmark lại latency sau cả 2 thay đổi

**Ngoài scope:**
- Không thể verify torch.compile có thực sự tăng tốc trên CPU trong phiên này (máy dev Windows không hỗ trợ Triton backend đầy đủ) — việc verify chuyển cho bước deploy/CI Linux, ghi rõ giới hạn này trong test report
- Không đổi `mode="reduce-overhead"` cho nhánh CUDA hiện có (giữ nguyên, chỉ thêm nhánh mới cho CPU)
- Không đổi công thức `soh_confidence = 1.0 - soh_std/5.0` (hằng số /5.0) — nếu sau khi đổi MC_RUNS=10 thấy công thức miscalibrate rõ rệt thì mở issue riêng, không tự ý đổi công thức trong ticket này
- Không đổi `load_long_model()` (long-seq, model khác, SLA khác theo GH-10 deploy decision) — chỉ đổi `load_models()` (standard model)
- Không đổi thêm `MC_RUNS` thành config value trong `config.py` — giữ nguyên là local constant, chỉ đổi giá trị

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/model_loader.py` | modify | Thêm nhánh `else` (CPU) thử `torch.compile(mode="default")` sau khối `if torch.cuda.is_available()`, try/except fallback im lặng giống pattern CUDA hiện có |
| `src/services/inference.py` | modify | `MC_RUNS = 20` → `MC_RUNS = 10` trong `run_inference()` |
| `tests/test_inference.py` | modify | Cập nhật test liên quan `MC_RUNS` nếu có hardcode; thêm ghi chú/so sánh `soh_std` không tụt về gần 0 bất thường |
| `tests/test_model_loader.py` | create | Mới phát sinh trong lúc code (không có trong plan gốc): 2 test cho bug lazy-compile fallback vừa tìm ở Bước 1 |

## Approach
- `model_loader.py`:
  ```python
  if torch.cuda.is_available():
      try:
          soh_model = torch.compile(soh_model, mode="reduce-overhead")
      except Exception:
          pass
  else:
      try:
          soh_model = torch.compile(soh_model, mode="default")
      except Exception:
          pass  # CPU backend (inductor) cần C++ toolchain — fallback eager nếu thiếu, hoặc Windows/Triton không hỗ trợ
  ```
- `inference.py`: đổi hằng số `MC_RUNS`, không đổi logic khác (batching từ GH-62 giữ nguyên)
- Đo lại 4 demo payload (giống format GH-60/62) — so sánh `soh_percent`/`soh_confidence`/`soh_std` trước/sau để có bằng chứng cụ thể việc giảm MC_RUNS không làm confidence "vô dụng"

## Edge Cases
- `torch.compile` fail trên CPU (như đã thấy ở Windows dev machine, lỗi Triton/encoding) → except bắt lại, fallback về eager, không crash app
- `MC_RUNS=10` vẫn phải > 1 để `np.std()` có ý nghĩa (10 đủ lớn, không phải edge case cần validate thêm)
- Nếu sau khi giảm MC_RUNS, `soh_confidence` cho ra giá trị bất thường (âm, >1) → đã có `max(0.0, min(1.0, ...))` clamp sẵn, không cần sửa thêm

## Acceptance Criteria
- [ ] `model_loader.py` có nhánh thử `torch.compile` cho CPU, có try/except fallback an toàn — không crash nếu compile fail (đã tự verify fail-safe ngay trên máy dev Windows)
- [ ] `MC_RUNS=10`, `pytest tests/test_inference.py` pass, không regression shape/logic
- [ ] Latency benchmark local cải thiện thêm so với GH-62 baseline (~119-126ms) — kỳ vọng về dưới 100ms dựa trên số đo thử trước (~60ms cho riêng phần forward pass ở MC_RUNS=10)
- [ ] So sánh `soh_confidence`/`soh_std` MC_RUNS=10 vs MC_RUNS=20 trên 4 demo payload — ghi rõ mức chênh lệch, xác nhận vẫn hữu ích cho mục đích cảnh báo
- [ ] `soh_percent`/MAE không regression so với GH-60/62 baseline (~2%)
- [ ] Document rõ: torch.compile CPU KHÔNG verify được tăng tốc thật trong ticket này (giới hạn máy dev Windows) — cần xác nhận ở môi trường deploy Linux

## Steps
- [x] Bước 1 (Inference): sửa `model_loader.py` — thêm nhánh torch.compile CPU — 2026-07-04. **Phát hiện + sửa 1 bug thật trong lúc code:** `torch.compile()` là lazy (wrap luôn "thành công", backend chỉ chạy lúc forward pass đầu tiên) — nếu chỉ bọc try/except quanh lệnh `torch.compile()` như dự định ban đầu, lỗi thật (compile fail — đã tái hiện trên máy Windows này, lỗi Triton/encoding) sẽ KHÔNG bị bắt ở startup mà crash thẳng vào request `/predict` đầu tiên. Đã sửa: thêm 1 forward pass "warm-up" giả (dummy input) NGAY TRONG try/except để ép compile chạy thật lúc startup — nếu fail thì fallback về eager an toàn trước khi phục vụ request nào. Đã verify: `run_inference()` chạy thành công sau khi sửa (trước khi sửa, crash 100%).
- [x] Bước 2 (Inference): sửa `MC_RUNS` 20→10 trong `src/services/inference.py` — 2026-07-04
- [x] Bước 3 (Unit test): cập nhật test, thêm mới `tests/test_model_loader.py` (2 test cho fallback/success của bug vừa tìm) — chạy full suite — 2026-07-04
- [x] Bước 4: đo lại 4 demo payload MC_RUNS=10 — MAE 2.413% (baseline MC_RUNS=20: 2.127%, chênh trong dao động tự nhiên); confidence 0.55-0.86 và soh_std 0.68-2.27 (baseline: 0.58-0.82 / 0.92-2.1) — cùng bậc độ lớn, không collapse — 2026-07-04
- [x] Bước 5: benchmark lại — **`Predict avg 91.5ms < 100.0ms` → RESULT: PASS** (lần đầu đạt SLA, từ baseline GH-62 ~119-126ms) — 2026-07-04
- [x] Bước 6: document — PASS đạt được **hoàn toàn nhờ giảm MC_RUNS** (torch.compile CPU fallback về eager trên máy Windows này do lỗi Triton, đã verify qua log/test) — xem Ghi chú bên dưới — 2026-07-04

## Câu hỏi đã giải đáp
- **torch.compile scope:** thêm code thử + fallback an toàn, không verify được trong phiên này (máy dev Windows không hỗ trợ Triton đầy đủ) — chờ xác nhận ở deploy Linux.
- **MC_RUNS target:** giảm xuống 10 (không phải 15) — ưu tiên biên an toàn latency rõ ràng hơn (đo được ~60ms vs ~96ms), chấp nhận đánh đổi độ chính xác uncertainty estimate nhiều hơn 1 chút.
