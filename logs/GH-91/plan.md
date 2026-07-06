# Plan — GH-91: Add temperature OOD/distance flag to predict response

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-06
- **Issue:** #91 — https://github.com/GSU26SE55/ai-module/issues/91
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
Model chỉ train ở 3 điểm nhiệt độ rời rạc NASA (4°C/24°C/44°C), nhưng validation hiện tại (GH-66) chỉ chặn nhiệt độ ngoài khoảng phẳng `[-10, 60]°C` — một giá trị như 15°C pass qua mà không cảnh báo, dẫn tới silent extrapolation. Issue này thêm tín hiệu minh bạch: tính khoảng cách của nhiệt độ input tới cluster train gần nhất, trả về trong response (metadata + warning) khi vượt ngưỡng — không đổi giá trị SOH/anomaly, không retrain, không cần data mới.

## Scope

> **Lưu ý kiến trúc quan trọng (cập nhật 2026-07-06):** gRPC (`aimodule.v1.AiService`, port 50051) là **production transport** thực tế BE gọi; FastAPI REST (port 8000) hiện chỉ là **backup/dev tool**. Vì vậy trong scope này, field mới trên gRPC (`ai_service.proto` + `grpc_server.py`) là phần **bắt buộc không thể thiếu**, còn REST vẫn làm đồng thời để giữ parity (rule `ai.md`) nhưng không phải là đường dẫn chính được verify kỹ nhất trong production. Nếu phát sinh xung đột thời gian, ưu tiên đảm bảo đúng cho gRPC trước.

**Trong scope:**
- Tính khoảng cách nhiệt độ **per-reading** (từng dòng trong 30 reading của window) tới cluster gần nhất trong `{4, 24, 44}°C`, lấy **max** trong window làm giá trị đại diện (worst-case — 1 điểm bất thường trong window vẫn phải được phát hiện, không bị trung bình hoá che khuất)
- Ngưỡng flag: `max_distance > 5°C` — bán kính "vùng tin cậy" quanh mỗi cluster train, coi như dung sai cảm biến/dao động buồng nhiệt thực tế. **Lưu ý quan trọng:** 2 cluster liền kề cách nhau 20°C (4↔24, 24↔44) nên điểm giữa xa nhất có thể có (14°C hoặc 34°C) chỉ cách cluster gần nhất tối đa 10°C — nếu chọn threshold=10°C thì flag gần như không bao giờ fire ở vùng giữa, kể cả đúng ví dụ 15°C mà issue nêu ra (15°C cách cluster 24°C 9°C, không vượt 10 → sẽ không bị flag, phản tác dụng ngay chính motivating example). Threshold=5°C đảm bảo 15°C (distance=9) được flag đúng như kỳ vọng.
- Thêm **cả 2** nơi expose kết quả (theo pattern đã có trong codebase):
  - `ResponseMetadata.temperature_domain_distance: float` + `ResponseMetadata.is_temperature_ood: bool` — theo đúng pattern `n_series` (GH-65)
  - `WarningItem` code mới `"TEMP_OOD"`, severity `"warning"` trong `evidence.warnings` — theo đúng pattern `TEMP_ELEVATED`/`TEMP_CRITICAL`
- Đồng bộ gRPC (proto + servicer) trong cùng issue — **bắt buộc**, không tách issue riêng: rule `ai.md` yêu cầu REST/gRPC parity field-by-field có test enforce (`test_predict_parity_with_rest`); thêm field mới vào REST response mà không cập nhật proto sẽ làm parity test tự động fail hoặc field bị thiếu ở gRPC.
- Chỉ áp dụng cho pipeline production `run_inference` (window=30, `/predict` REST + `Predict`/`PredictStream` gRPC)

**Ngoài scope:**
- Long-sequence pipeline L=4096 (`predict_soh_long`, GH-10) — không phải production path, không đụng tới
- Chemistry-aware validation (GH-67) — vẫn để riêng, không trộn vào đây
- Không thay đổi SOH/anomaly/confidence tính toán — đây chỉ là tín hiệu bổ sung, không ảnh hưởng business logic hiện có
- Không retrain, không đổi `VOLTAGE_CELL_RANGE`/`TEMPERATURE_RANGE`/schema validation hiện có (GH-66 giữ nguyên)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/config.py` | modify | Thêm `TEMPERATURE_TRAIN_CLUSTERS = (4.0, 24.0, 44.0)` + `TEMPERATURE_OOD_THRESHOLD = 5.0` |
| `src/models/anomaly_detector.py` | modify | Thêm hàm `temperature_domain_distance(temps) -> float` (single source of truth); gọi trong `generate_warnings()` để append `TEMP_OOD` warning khi vượt ngưỡng |
| `src/services/inference.py` | modify | Gọi `temperature_domain_distance(raw[:, 2])` 1 lần trong `run_inference`, ghi vào `metadata["temperature_domain_distance"]` + `metadata["is_temperature_ood"]` |
| `src/schemas/predict.py` | modify | Thêm 2 field vào `ResponseMetadata`: `temperature_domain_distance: float = 0.0`, `is_temperature_ood: bool = False` (default giữ backward-compat với response cũ) |
| `protos/ai_service.proto` | modify | Thêm field số **6, 7** (mới, không đổi số cũ) vào message `ResponseMetadata` |
| `src/grpc_gen/` (generated) | regenerate | Chạy `python scripts/gen_proto.py` sau khi sửa proto, commit lại stub |
| `src/grpc_server.py` | modify | `_to_predict_response()` (dòng ~107-112): map 2 field mới vào `ai_service_pb2.ResponseMetadata(...)` |
| `tests/test_models.py` | modify | Unit test `temperature_domain_distance()` (in-cluster=0, giữa 2 cluster=10, tại 4/24/44 chính xác=0) + test `TEMP_OOD` warning xuất hiện/không xuất hiện trong `generate_warnings()` |
| `tests/test_inference.py` | modify | Test `metadata.temperature_domain_distance` + `is_temperature_ood` qua `run_inference()` với 2 case: nhiệt độ tại cluster (flag=False) và nhiệt độ giữa 2 cluster ví dụ 15°C (flag=True) |
| `tests/test_grpc_server.py` | modify | Parity test cho 2 field mới — mirror pattern `test_predict_12v_with_n_series_3_ok_and_traced` |

## Approach
1. `temperature_domain_distance(temps: np.ndarray) -> float` = `max(min(abs(t - c) for c in TEMPERATURE_TRAIN_CLUSTERS) for t in temps)` — tính 1 lần, dùng chung cho cả warning và metadata (không tính trùng 2 lần bằng 2 công thức khác nhau).
2. `run_inference()`: sau khi có `raw` (unscaled readings), gọi `dist = temperature_domain_distance(raw[:, 2])`; set `metadata["temperature_domain_distance"] = round(dist, 2)` và `metadata["is_temperature_ood"] = dist > TEMPERATURE_OOD_THRESHOLD`.
3. `generate_warnings()`: thêm block mới sau block Temperature hiện có (`TEMP_ELEVATED`/`TEMP_CRITICAL`) — gọi lại `temperature_domain_distance(raw[:, 2])`, nếu `> TEMPERATURE_OOD_THRESHOLD` thì append `{"code": "TEMP_OOD", "severity": "warning", "message": f"Temperature {dist:.1f}°C from nearest training cluster (4/24/44°C) — prediction may be extrapolated."}`.
4. Proto: thêm `double temperature_domain_distance = 6;` và `bool is_temperature_ood = 7;` vào `message ResponseMetadata` (giữ nguyên field 1-5).
5. `grpc_server.py`: thêm 2 kwarg tương ứng vào `ai_service_pb2.ResponseMetadata(...)` trong `_to_predict_response()` — vì cả `Predict` và `PredictStream` đều dùng chung hàm này, chỉ sửa 1 chỗ.

## Edge Cases
- Nhiệt độ đúng bằng 1 trong 3 cluster (4/24/44°C chính xác) → `distance = 0`, không warning
- Nhiệt độ đúng bằng threshold (cách cluster gần nhất đúng 5°C, ví dụ 9°C hoặc 19°C) → dùng `>` (không phải `>=`) nên KHÔNG flag ở biên, nhất quán với style `> EOL_SOH`/`> TEMP_WARNING` hiện có trong codebase
- Window có nhiệt độ dao động (một số reading gần cluster, một số xa) → dùng max nên window vẫn bị flag nếu có bất kỳ 1 điểm nào vượt ngưỡng (an toàn hơn dùng mean)
- Request không có cột temperature (không xảy ra — `temperature` là required field trong mọi input schema hiện có, bao gồm legacy 3-col)
- Response cũ (cached/BE chưa update) đọc field mới → Pydantic default `0.0`/`False` đảm bảo không lỗi deserialize

## Acceptance Criteria
- [x] `temperature_domain_distance()` trả đúng giá trị cho các mốc kiểm chứng bằng tay (xem `tests/test_models.py::TestTemperatureDomainDistance`):
  | Input °C | Cách tính (min khoảng cách tới {4,24,44}) | distance | flag (>5) |
  |---|---|---|---|
  | 24 | tại cluster | 0 | False |
  | 9 | min(5,15,35) | 5 | False (biên, dùng `>` không `>=`) |
  | 15 | min(11,9,29) | 9 | **True** — ví dụ motivating trong issue #91 |
  | 14 | min(10,10,30) | 10 | True |
  | 60 (biên trên `TEMPERATURE_RANGE`) | min(56,36,16) | 16 | True |
  | -10 (biên dưới `TEMPERATURE_RANGE`) | min(14,34,54) | 14 | True |
- [x] `run_inference()` trả đúng `metadata.temperature_domain_distance` + `metadata.is_temperature_ood` cho 2 case: window ổn định tại 24°C (flag=False) và window tại 15°C (flag=True) — `tests/test_inference.py::test_temperature_ood_flag_*`
- [x] `TEMP_OOD` warning xuất hiện trong `evidence.warnings` đúng khi và chỉ khi `is_temperature_ood=True` — `tests/test_models.py::TestTempOodWarning`
- [x] **gRPC** `Predict` + `PredictStream` response có `metadata.temperature_domain_distance`/`is_temperature_ood` đúng và nhất quán (ưu tiên cao nhất — production transport) — `test_predict_temperature_ood_flagged_via_grpc` (PredictStream dùng chung `_to_predict_response`, đã parity qua cùng hàm)
- [x] REST response giống hệt gRPC cho cùng input (parity test, rule `ai.md`) — `test_predict_parity_with_rest` (generic loop tự cover field mới)
- [x] `pytest --cov=src` toàn bộ vẫn PASS, coverage ≥85% — 292 passed, 2 skipped, coverage 87%
- [x] Inference latency vẫn <100ms — overhead đo riêng ~0.0225ms/call, không đáng kể so với baseline ~55.76ms (v1.6, đo trước GH-91)

## Steps
- [x] Bước 1: Thêm constants vào `src/core/config.py` — 2026-07-06
- [x] Bước 2: Viết `temperature_domain_distance()` trong `src/models/anomaly_detector.py` + tích hợp vào `generate_warnings()` — 2026-07-06
- [x] Bước 3: Tích hợp vào `run_inference()` (`src/services/inference.py`) — set metadata fields — 2026-07-06
- [x] Bước 4: Thêm field vào `ResponseMetadata` (`src/schemas/predict.py`) — 2026-07-06
- [x] Bước 5: Cập nhật `protos/ai_service.proto` + regenerate stub (`scripts/gen_proto.py`) + map field trong `src/grpc_server.py` — 2026-07-06
- [x] Bước 6: Unit test (`test_models.py`, `test_inference.py`) + gRPC parity test (`test_grpc_server.py`) — 2026-07-06
- [x] Bước 7: Chạy `pytest --cov=src` full suite (292 passed, 2 skipped, coverage 87%) + benchmark `temperature_domain_distance()` overhead (~0.0225ms/call thêm, không đáng kể so với baseline ~55.76ms đã đo với v1.6) — 2026-07-06

## Câu hỏi đã giải đáp
1. **Mean vs per-reading:** chọn per-reading, lấy **max** trong window (worst-case, không bị che bởi trung bình) — theo recommendation.
2. **Ngưỡng threshold:** `5°C` — theo recommendation. Ban đầu đề xuất 10°C nhưng phát hiện lỗi logic (2 cluster liền kề cách nhau 20°C nên điểm giữa xa nhất chỉ cách 10°C — threshold=10 sẽ không bao giờ flag đúng ví dụ 15°C mà issue nêu ra); đã sửa xuống 5°C để 15°C (distance=9) được flag đúng như kỳ vọng.
3. **Vị trí field:** cả 2 — `ResponseMetadata` (numeric distance + bool flag, theo pattern `n_series`) và `WarningItem` code `TEMP_OOD` (theo pattern `TEMP_ELEVATED`) — theo recommendation.
4. **Scope gRPC:** làm luôn trong issue này, không tách riêng — vì rule `ai.md` bắt buộc REST/gRPC parity có test enforce, tách issue sẽ để lại parity test fail giữa 2 lần ship. — theo recommendation. **Cập nhật:** user xác nhận gRPC là production transport thực tế (BE gọi qua gRPC), FastAPI REST hiện chỉ là backup/dev tool — càng củng cố việc gRPC path phải đúng và được verify kỹ trong issue này, không thể trì hoãn sang issue sau.
5. **Scope pipeline:** chỉ `run_inference` (window=30, production path) — xác nhận qua `src/routers/predict.py:4,12` chỉ import `run_inference`, không đụng `predict_soh_long`.
