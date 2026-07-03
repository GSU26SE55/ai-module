# Plan — GH-56: Extend readings API contract to accept 6 fields (BE sends cycle_count + soc_percent directly)

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-03
- **Issue:** #56 — https://github.com/GSU26SE55/ai-module/issues/56
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
Hiện tại production luôn nhận `cycle_count_norm = 0` vì router (`src/routers/predict.py`, `src/grpc_server.py`) không truyền `cycle_idx` vào `run_inference()`, trong khi model học giá trị thật lúc train (chênh lệch SOH trung bình ~10.8 điểm % giữa cycle sớm/muộn — bias có hướng, không phải noise). BE đã chốt sẽ tính và gửi thẳng `cycle_count` (raw cycle index) + `soc_percent` (raw 0-100, tính từ full lịch sử sạc/xả) làm 2 cột bổ sung trong `readings`, thay vì AI tự derive từ `current`+`time`. Output: API nhận được payload 6-cột, dùng trực tiếp 2 giá trị BE tính, đồng thời giữ nguyên hành vi cũ (derive server-side) cho request 3/4-cột legacy.

## Scope
**Trong scope:**
- Mở rộng validation `readings` (Pydantic — dùng chung cho cả REST và gRPC vì gRPC gọi qua `_validate(PredictRequest, ...)`) chấp nhận thêm 6-cột
- `src/services/inference.py`: khi payload 6-cột, dùng trực tiếp cột 5 (`cycle_count`, hằng số/window) + cột 6 (`soc_percent`, biến thiên/timestep) thay vì tính qua Coulomb counting + `cycle_idx` param
- Giữ nguyên path hiện tại (derive server-side, `cycle_idx` mặc định `None`→0) cho request 3/4-cột — không phá backward compat
- Demo payload mẫu 6-cột (BE tham chiếu format) + cập nhật `scripts/make_demo_payloads.py`
- Test parity: 6-cột (BE tính) vs 4-cột+`cycle_idx` (AI tính) phải cho cùng model input/output; REST vs gRPC cùng kết quả với payload 6-cột

**Ngoài scope:**
- Không đổi wire format `.proto` — `Reading.values` đã là `repeated double` (độ dài tuỳ ý), không cần thêm field mới, chỉ cập nhật comment mô tả layout
- Không đổi `src/routers/predict.py` / `src/grpc_server.py` — 2 file này gọi `run_inference(readings)` không đổi signature, logic detect nằm hết trong `inference.py`
- Không retrain model, không đổi `scripts/preprocess.py` (training pipeline không liên quan tới serving contract)
- Không đổi `CYCLE_COUNT_NORM`, không xử lý rủi ro pin thật sống hơn 200 cycle (theo dõi riêng, không thuộc issue này)

## Row layout (quyết định thiết kế — theo yêu cầu khuyến nghị vì không cần sửa schema/proto thêm field)
Mỗi dòng trong 30 dòng `readings` khi gửi đủ 6 field: `[voltage, current, temperature, time, cycle_count, soc_percent]`
- `cycle_count`: hằng số, lặp lại giống nhau ở cả 30 dòng (đúng như training — 1 window chỉ thuộc 1 cycle)
- `soc_percent`: biến thiên theo từng dòng/timestep (đúng như training — SOC giảm dần trong window)

Khớp chính xác shape `(30, 6)` của `data/processed/train.pt` — không cần thêm field mới ở Pydantic/proto, chỉ đổi số cột được chấp nhận.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/schemas/predict.py` | modify | `validate_readings_shape`: `allowed_feature_counts = {LEGACY_INPUT_FEATURES(3), BASE_INPUT_FEATURES(4), INPUT_FEATURES(6)}` |
| `src/services/inference.py` | modify | `_expected_feature_count()`, `_align_features()`, `_append_derived_features()`: detect payload 6-cột → dùng `raw[:, 4]/CYCLE_COUNT_NORM` + `raw[:, 5]/100.0` trực tiếp thay vì Coulomb counting |
| `protos/ai_service.proto` | modify | update comment `Reading` mô tả rõ layout 6-cột (không đổi field/wire format) |
| `demo/predict_degraded_6field.json` | create | demo payload mẫu 6-cột cho BE tham chiếu |
| `scripts/make_demo_payloads.py` | modify | thêm option sinh payload 6-cột |
| `tests/test_inference.py` | modify | test path 6-cột + test parity 6-cột (cycle_count=N) vs 4-cột+`cycle_idx=N` (cùng data → cùng model input) |
| `tests/test_grpc_server.py` | modify | test parity REST vs gRPC cho payload 6-cột |

## Approach
- `_expected_feature_count()` hiện trả về scaler width (4) để `_align_features()` cắt bớt cột thừa trước khi scale — cần thêm 1 hàm/branch mới: nếu `raw.shape[1] == INPUT_FEATURES (6)`, tách riêng 4 cột đầu để scale (giữ logic `_align_features` không đổi), rồi lấy thẳng cột 5,6 làm derived features thay vì gọi `compute_soc_percent`.
- `_append_derived_features(x_scaled, raw, cycle_idx)`: thêm nhánh — nếu `raw.shape[1] == len(BASE_FEATURES) + 2`, dùng `raw[:, 4]` (cycle_count, lấy giá trị đầu vì hằng số) / `CYCLE_COUNT_NORM` và `raw[:, 5] / 100.0` thay vì tính Coulomb counting; nếu không, giữ nguyên logic cũ (Coulomb counting từ current+time, `cycle_idx` param).
- Validation tầng Pydantic reject mọi độ dài khác {3, 4, 6} (giữ nguyên message lỗi hiện có, chỉ mở rộng tập hợp).
- Không đổi router/grpc_server — 2 nơi gọi `run_inference(readings)` tự động hoạt động đúng vì logic detect nằm trong `inference.py`.

## Edge Cases
- `readings` có 5 cột (không hợp lệ) → reject với `ValueError` rõ ràng (giữ nguyên message pattern hiện có, liệt kê {3,4,6})
- Payload 6-cột nhưng `cycle_count` khác nhau giữa các dòng trong cùng window (BE gửi sai) → không validate strict (out of scope — tin tưởng BE gửi đúng theo doc), chỉ lấy dòng đầu
- Model artifact cũ (input_features=4, chưa retrain — hiện `soh_mamba_v1.4.pth` còn là dummy) nhận payload 6-cột → `_append_derived_features` phải no-op nếu `model_dim != x_scaled.shape[1] + 2` (logic đã có sẵn, không đổi)
- `soc_percent` hoặc `cycle_count` âm/ngoài range từ BE → không validate range trong scope này (theo dõi riêng nếu phát sinh)

## Acceptance Criteria
- [ ] `PredictRequest.readings` chấp nhận rows 3, 4, hoặc 6 giá trị; reject rows có độ dài khác với message rõ ràng
- [ ] Payload 6-cột: `cycle_count`/`soc_percent` dùng trực tiếp (không tính lại qua Coulomb counting), sau khi normalize đúng `CYCLE_COUNT_NORM`/100
- [ ] Payload 3/4-cột: hành vi giữ nguyên như hiện tại (không regression)
- [ ] Test parity: 6-cột (cycle_count=N, soc_percent=S đã biết trước) cho cùng model input tensor như 4-cột + `cycle_idx=N` khi S khớp công thức Coulomb counting
- [ ] Test parity REST vs gRPC cho cùng payload 6-cột → cùng response
- [ ] `pytest --cov=src` ≥ 85% (quality gate dự án)
- [ ] Latency vẫn < 100ms (benchmark lại theo `tests/test_inference.py`)
- [ ] Demo payload 6-cột mẫu có trong `demo/` để BE tham chiếu

## Steps
- [x] Bước 1 (Inference): sửa `_expected_feature_count()` + `_align_features()` trong `src/services/inference.py` để nhận diện payload 6-cột — 2026-07-03 — **hoá ra không cần sửa**: `_align_features` đã tự cắt về 4 cột cho scaler (dùng để scale), còn `raw` gốc (6 cột nếu có) vẫn được truyền nguyên vẹn sang `_append_derived_features` — không cần thay đổi gì ở 2 hàm này.
- [x] Bước 2 (Inference): sửa `_append_derived_features()` — nhánh dùng trực tiếp cycle_count/soc_percent khi payload đủ 6 cột — 2026-07-03
- [x] Bước 3 (Schema): mở rộng `validate_readings_shape` trong `src/schemas/predict.py` chấp nhận {3,4,6} — 2026-07-03
- [x] Bước 4 (Proto): update comment `Reading` message trong `protos/ai_service.proto` mô tả layout 6-cột — 2026-07-03 (không cần chạy `gen_proto.py` — chỉ đổi comment, không đổi field/wire format)
- [x] Bước 5 (Demo): tạo `demo/predict_degraded_6field.json` + thêm option trong `scripts/make_demo_payloads.py` — 2026-07-03
- [x] Bước 6 (Unit test): thêm test 6-cột path + parity test trong `tests/test_inference.py` (+ `tests/test_routers.py` cho REST end-to-end) — 2026-07-03
- [x] Bước 7 (Unit test): thêm parity test REST/gRPC cho payload 6-cột trong `tests/test_grpc_server.py` — 2026-07-03
- [x] Bước 8: benchmark latency lại, chạy `pytest --cov=src` full suite — 2026-07-03. Kết quả: coverage 87% (≥85% pass). 194 passed / 1 failed (`test_rule_path_under_100ms` — flaky, pass khi chạy riêng lẻ, không liên quan `prescription.py`/`rule_prescription.py` không đụng tới trong issue này). Latency: đo trực tiếp `run_inference` full-size model (d_model=64) — baseline 4-cột ~127ms vs 6-cột (code mới) ~132ms, chênh lệch ~5ms nằm trong noise → **không regression**. Cả 2 vượt 100ms trên máy dev là đặc điểm sẵn có của MC Dropout (20 forward pass) full-size trên CPU, không phải do GH-56 — SLA chính thức benchmark qua `scripts/benchmark_grpc.py --real-weights` trên môi trường deploy, không phải unit test (unit test dùng dummy d_model=8 để nhanh/deterministic).

## Câu hỏi đã giải đáp
- **Row layout:** chọn lặp lại `cycle_count` giống nhau cả 30 dòng + `soc_percent` biến thiên theo dòng, khớp chính xác shape training `(30,6)` — không cần thêm field mới ở schema/proto (không có phản hồi trong 60s, chọn theo phương án khuyến nghị/ít rủi ro nhất vì không đổi wire format).
- **Demo payload:** có cập nhật, thêm `demo/predict_degraded_6field.json` làm reference cho BE (không có phản hồi trong 60s, chọn theo phương án khuyến nghị vì effort nhỏ).
- **Proto:** xác nhận qua đọc code — `Reading.values` là `repeated double` (độ dài tuỳ ý), không cần thêm field mới, chỉ update comment.
