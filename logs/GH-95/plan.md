# Plan — GH-95: Optimize production anomaly F1 — causal degradation-rate rule (per-battery state)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-09
- **Issue:** #95 — https://github.com/GSU26SE55/ai-module/issues/95
- **Sprint:** Sprint 4 (due 2026-07-11)

## ⚠️ REVISION — approach v2 (thay thế hoàn toàn plan v1)

Plan v1 (feed "degradation residual" — soh_predicted vs population fade curve — vào
IsolationForest) đã bị **loại bỏ sau khi đo thực nghiệm**, không phải bị bỏ giữa chừng:

1. Refit IsolationForest với residual feature (58-dim): F1 val 0.4512, test 0.3003 —
   **không đổi** so baseline 57-dim (0.4533/0.2972). Trong nhiễu thống kê.
2. Để loại trừ "chưa đúng feature" khỏi "thông tin không tồn tại": train **supervised**
   classifier (LogisticRegression + RandomForest, biết nhãn thật) trên chính 57-dim +
   58-dim. Kết quả: **AUC chỉ 0.49–0.58** (random = 0.5) — kể cả với thông tin tối đa
   (supervised) cũng không tách được nhãn. Kết luận: residual-từ-population không mang
   tín hiệu thật, không phải do chọn sai model/threshold.
3. Test tiếp **causal rate** (so sánh SOH hiện tại với SOH k cycle *trước đó* của
   CHÍNH pin đó — cần state, khác population residual không cần state):
   AUC nhảy lên **0.80–0.84** (k=2), F1 threshold đơn giản đạt **0.605 val / 0.535 test**.
4. Nhưng feed causal rate vào IsolationForest (58-dim) **vẫn không cải thiện** —
   57 chiều spectral (đa số nhiễu với nhãn này) lấn át tín hiệu causal rate trong
   cơ chế contamination-splitting của IsolationForest.
5. **Rule trực tiếp trên causal rate** (không qua IsolationForest): F1 **0.605 val /
   0.535 test** — kết quả tốt nhất tìm được, dùng làm approach chính thức.

**Kết luận kỹ thuật:** nhãn rate-based (suy thoái nhanh) không thể suy ra từ 1 window
tĩnh (residual-population hay bất kỳ feature tĩnh nào khác) — đây là information
constraint, không phải feature-engineering problem. Chỉ có cách duy nhất mang lại tín
hiệu thật: so sánh pin với chính lịch sử gần nhất của nó → **bắt buộc cần state
per-battery**, điều mà plan v1 đã loại khỏi scope. User đã xác nhận đổi hướng sau khi
xem bằng chứng thực nghiệm (không phải đoán).

## Mục tiêu
Thêm 1 rule classification mới dựa trên **causal degradation rate** (so với lịch sử
gần nhất của chính battery đó, lưu trong AI module) — kết hợp với `classify_anomaly()`
hiện có (IsolationForest 57-dim giữ nguyên, KHÔNG đổi). F1 cải thiện từ baseline
0.30–0.45 lên ~0.53–0.61 — **chưa đạt 0.80**, báo cáo trung thực, đây là cải thiện có
căn cứ thực nghiệm, không phải cách duy nhất/đảm bảo đạt target cứng của `ai.md`.

## Scope
**Trong scope:**
- Module state per-battery: `src/services/battery_history.py` — in-memory, thread-safe,
  bounded, keyed bằng `battery_id` (đã có sẵn trong request, KHÔNG đổi BE contract)
- Hàm causal rate: so SOH hiện tại với SOH k=2 cycle trước (best AUC theo thực nghiệm)
  của cùng battery
- `RATE_THRESHOLD` config constant — train p90 của local fade rate, **cùng phương
  pháp/threshold với GH-70** (đã GVHD duyệt), tính lại trên split hiện tại (post GH-88)
- Mở rộng `classify_anomaly()` — thêm tham số `causal_rate: float | None`, escalate
  1 tier khi rate vượt ngưỡng, giữ nguyên hành vi cũ khi `causal_rate=None` (cold start /
  thiếu cycle_count / thiếu battery_id)
- Thread `battery_id` + `raw_cycle_count` vào `run_inference()`, record lịch sử SAU khi
  tính rate (rate dùng lịch sử TRƯỚC điểm hiện tại — đúng nghĩa causal)
- Update REST router + gRPC servicer truyền `battery_id` xuống `run_inference()`
- Unit test cho `battery_history.py` (cold start, thread-safety, eviction/bounded)
  + integration test `/predict` gọi liên tiếp cùng battery_id → classification escalate
- Latency re-benchmark (state lookup O(1)/O(k), kỳ vọng không đổi đáng kể — verify)
- Document rõ giới hạn: in-memory = mất state khi restart, KHÔNG an toàn nếu chạy nhiều
  replica (single-instance deployment giả định — đúng với scope capstone)

**Ngoài scope:**
- Không đổi IsolationForest (giữ nguyên `isolation_forest_v1.6.pkl`, 57-dim, không
  version bump — approach v1's `ISO_FOREST_VERSION` decoupling đã bị revert vì không
  còn cần thiết)
- Không đổi Mamba, không đổi BE contract
- Không thêm persistent storage (Redis/DB) cho state — in-memory đủ cho scope capstone,
  ghi rõ limitation thay vì over-engineer
- Không đảm bảo đạt F1 > 0.80 — báo cáo trung thực số đạt được (0.53–0.61)
- Không sửa `.claude/rules/tech/ai.md` — note trong PR, user tự cập nhật nếu đồng ý

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/battery_history.py` | create | in-memory store: `record(battery_id, cycle, soh)`, `causal_rate(battery_id, k=2) -> float \| None`. RLock, `deque(maxlen=8)` per battery |
| `src/core/config.py` | modify | thêm `RATE_THRESHOLD` (train p90 local fade rate, cite GH-70 methodology) + `CAUSAL_RATE_K = 2` |
| `src/models/anomaly_detector.py` | modify | `classify_anomaly()` thêm param `causal_rate: float \| None = None`, escalate 1 tier nếu vượt `RATE_THRESHOLD` |
| `src/services/inference.py` | modify | `run_inference()` thêm `battery_id` param; gọi `battery_history.causal_rate()` TRƯỚC, dùng trong `classify_anomaly()`, rồi `battery_history.record()` SAU |
| `src/routers/predict.py` | modify | truyền `request.battery_id` xuống `run_inference()` |
| `src/grpc_server.py` | modify | truyền `battery_id` xuống `run_inference()` (cả `Predict` và `PredictStream`) |
| `scripts/compute_rate_threshold.py` | create | script nhỏ tính `RATE_THRESHOLD` từ train set hiện tại (tái dùng `eval_anomaly.py`'s `local_fade_rate`/`smooth_soh`/`RATE_PERCENTILE`), in giá trị để dán vào `config.py` — không phải artifact, chỉ để reproducible |
| `tests/test_battery_history.py` | create | unit test: cold start (None), causal_rate đúng công thức, bounded history (eviction), thread-safety cơ bản |
| `tests/test_anomaly_detector.py` hoặc file liên quan | modify | test `classify_anomaly()` với `causal_rate` các case: None (giữ nguyên hành vi cũ), vượt ngưỡng (escalate), dưới ngưỡng (không đổi) |
| `tests/test_inference.py` | modify | test `run_inference()` với `battery_id` — gọi liên tiếp cùng battery, verify causal_rate được dùng đúng (record sau khi tính rate) |

## Approach
1. `battery_history.py`: `_history: dict[str, deque[tuple[float, float]]]` (cycle, soh),
   `maxlen=8`, `RLock` bảo vệ (giống pattern `_MC_LOCK` đã có trong `inference.py`).
   `causal_rate(battery_id, k=2)`: lấy điểm hiện tại mới nhất đã ghi và điểm cách đó tối
   đa k bước (hoặc điểm cũ nhất nếu chưa đủ k) → `-(soh_now - soh_then) / (cycle_now -
   cycle_then)`. Return `None` nếu chưa có lịch sử, `dc <= 0`, hoặc thiếu battery_id.
2. `run_inference(readings, cycle_idx, n_series, battery_id)`:
   - Sau khi có `raw_cycle_count` + `soh_median`: gọi
     `rate = battery_history.causal_rate(battery_id)` (dùng lịch sử TRƯỚC điểm này)
   - `classification = classify_anomaly(score, soh_median, causal_rate=rate)`
   - Cuối hàm: `battery_history.record(battery_id, raw_cycle_count, soh_median)`
3. `classify_anomaly(score, soh, causal_rate=None)`: giữ nguyên logic gốc tính `base`;
   nếu `causal_rate is not None and causal_rate > RATE_THRESHOLD`: escalate 1 tier
   (Normal→Degrading, Degrading→Failed, Failed giữ nguyên).
4. `RATE_THRESHOLD`: chạy `scripts/compute_rate_threshold.py` 1 lần, lấy số thật trên
   split hiện tại (đo được ở bước khảo sát: ~0.50 %SOH/cycle), hardcode vào `config.py`
   kèm comment nguồn gốc (train p90, seed 42, cùng phương pháp GH-70).

## Edge Cases
- `battery_id` thiếu/rỗng, `raw_cycle_count is None` → `causal_rate=None` → hành vi y hệt
  trước khi có GH-95 (không escalate, không lỗi)
- Request đầu tiên của 1 battery (cold start) → không đủ lịch sử → `None`
- `cycle_now <= cycle_then` (retry, out-of-order, duplicate) → `None` thay vì chia 0/âm
- Nhiều battery đồng thời → dict riêng theo `battery_id`, không đụng nhau
- **Giới hạn đã biết (ghi rõ trong docstring + PR):** in-memory, single-process — mất
  state khi restart server; KHÔNG đúng nếu deploy nhiều replica load-balanced (mỗi
  replica có state riêng, causal_rate sẽ sai/thiếu tuỳ replica nào nhận request). Chấp
  nhận được ở quy mô capstone (single container), ghi rõ để không ai hiểu nhầm là an
  toàn cho scale lớn hơn.

## Acceptance Criteria
- [ ] `battery_history.py` unit test đủ edge case (cold start, eviction, thread-safety)
- [ ] `classify_anomaly()` test: None giữ nguyên hành vi cũ, vượt ngưỡng escalate đúng 1 tier
- [ ] F1 đo lại trên val/test (rate-based label GH-70) — báo cáo trung thực số đạt được
  (kỳ vọng ~0.53–0.61, không phải 0.80) trong PR description
- [ ] `/predict` REST + gRPC vẫn đúng shape, gọi liên tiếp cùng `battery_id` → classification
  phản ứng đúng với rate tăng đột biến (integration test)
- [ ] Latency vẫn <100ms (`scripts/benchmark_grpc.py --real-weights`) — verify không giả định
- [ ] IsolationForest/Mamba không đổi — verify SOH prediction không đổi so với trước GH-95
- [ ] `pytest tests/ --cov=src` ≥85% PASS
- [ ] PR description nêu rõ giới hạn in-memory/single-instance

## Steps (AI)
- [x] Bước 1: `scripts/compute_rate_threshold.py` — RATE_THRESHOLD = 0.5016 %SOH/cycle (train p90, seed 42) — 2026-07-09
- [x] Bước 2: `src/services/battery_history.py` + unit test (13/13 pass) — 2026-07-09
- [x] Bước 3: `config.py` (`RATE_THRESHOLD=0.5016`, `CAUSAL_RATE_K=2`) + `classify_anomaly()` mở rộng + test (12/12 pass) — 2026-07-09
- [x] Bước 4: `run_inference()` thread `battery_id` + gọi battery_history đúng thứ tự (rate trước, record sau); refactor `_raw_cycle_count()` helper dùng chung; 31/31 test cũ vẫn pass — 2026-07-09
- [x] Bước 5: Router REST (`predict.py`), gRPC (`grpc_server.py::_predict_one`, dùng chung cho `Predict`+`PredictStream`), `prescription.py` truyền `battery_id`; 56/56 test cũ pass — 2026-07-09
- [x] Bước 6: Integration test escalation trong `test_inference.py` — bắt được bug thiết kế thật lúc viết test (`causal_rate()` ban đầu chỉ so 2 điểm lịch sử cũ, không dùng SOH request hiện tại) → sửa signature `causal_rate(battery_id, current_cycle, current_soh, k)`; full suite 343/343 pass — 2026-07-09
- [x] Bước 7: `benchmark_grpc.py --real-weights` — Predict avg 57.6ms/p95 73.4ms (trước GH-95: 60.6/77.5) — PASS, state lookup không ảnh hưởng latency — 2026-07-09
- [x] Bước 8: `pytest tests/ --cov=src` — 343/343 PASS, coverage 90% (≥85% target) — 2026-07-09

## Câu hỏi đã giải đáp
1. **Tách issue riêng hay dùng chung GH-70?** → Issue mới (GH-95) — GH-70 giữ scope paper.
2. **[Plan v1, đã bỏ] Cách tính degradation-rate khi stateless?** → Residual population —
   đã chứng minh thực nghiệm KHÔNG hoạt động (AUC ~0.5, kể cả supervised).
3. **[Plan v2] Hướng tiếp theo sau khi residual thất bại?** → User xác nhận: thêm state
   per-battery — đây là hướng DUY NHẤT có bằng chứng thực nghiệm hoạt động (AUC 0.80+).
4. **F1 mục tiêu?** → Không đạt 0.80 tuyệt đối với approach này (0.53–0.61) — user đồng ý
   tiếp tục, báo cáo trung thực, không cố tune ép số.
5. **In-memory state có đủ không, hay cần Redis/DB?** → In-memory đủ cho scope capstone
   (đã tự quyết định theo Simplicity First, ghi rõ giới hạn single-instance trong PR).
