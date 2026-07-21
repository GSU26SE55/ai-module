# Plan — GH-87: Prescription — embed nested prediction/anomaly/risk vào PrescribeResponse

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-21
- **Issue:** #87 — https://github.com/GSU26SE55/ai-module/issues/87
- **Sprint:** (chưa gán milestone)

> **Ghi chú:** thay thế plan cũ (05-07) — plan đó lỗi thời (tham chiếu `src/services/prescription.py`
> đã bị GH-96 refactor thành subpackage; đề xuất field proto 19-21 đã bị GH-81/82/83 chiếm).

## Mục tiêu
`PrescribeResponse` hiện chỉ trả 4 flat field rời rạc (`soh_percent`, `risk_level`, `priority`, `action_code`) — mất toàn bộ giá trị GH-86 (`health_stage`, `stage_probabilities`, `stage_confidence`, `is_borderline`, `soh_confidence`, `soh_std`, …) vì BE chỉ gọi Prescribe (predict chạy nội bộ trong `run_prescription`), không bao giờ thấy các field đó. Embed 3 block nested `prediction`/`anomaly`/`risk` (tái dùng `PredictionInfo`/`AnomalyInfo`/`RiskInfo` đã có sẵn từ `/predict`) vào `PrescribeResponse` cả REST và gRPC, giữ 4 flat field cũ (deprecated), và sửa comment sai của field `confidence`.

## Scope
**Trong scope:**
- Thêm `prediction: PredictionInfo`, `anomaly: AnomalyInfo`, `risk: RiskInfo` vào `PrescribeResponse` (Pydantic + proto), append-only (không đổi số field cũ)
- `orchestrator.run_prescription()` forward nguyên `prediction`/`anomaly`/`risk` dict từ `run_inference()` vào response
- `grpc_server._to_prescribe_response()` build 3 sub-message nested tương tự `_to_predict_response()`
- Sửa comment sai của field `confidence` trong proto (`PredictResponse.confidence = 9`) và `src/schemas/predict.py` (thực chất là `soh_confidence` MC Dropout, không phải IsolationForest score)
- Cập nhật `docs/grpc-integration-be.md`: ghi rõ flow khuyến nghị = gọi Prescribe (predict chạy nội bộ), Predict/PredictStream chỉ dùng cho real-time monitoring
- Test: parity field-by-field REST vs gRPC cho 3 block mới + assert `is_borderline`/`stage_confidence` xuất hiện

**Ngoài scope:**
- Xóa 13 flat field cũ của `PrescribeResponse`/`PredictResponse` (cần PR phối hợp BE — GH-61-style, `reserved` proto field)
- Đổi semantics classification/health_stage
- Refactor toàn bộ `docs/grpc-integration-be.md` (doc đang có nội dung stale khác như "4 features" — không thuộc scope GH-87, không đụng vào)
- Extract helper `_to_prediction_info()`/`_to_anomaly_info()`/`_to_risk_info()` dùng chung cho cả `_to_predict_response` — Surgical Changes: chỉ thêm mapping cho Prescribe, không refactor code Predict đang chạy tốt

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `protos/ai_service.proto` | modify | `PrescribeResponse`: append `PredictionInfo prediction = 24; AnomalyInfo anomaly = 25; RiskInfo risk = 26;`. Field 19-21 issue gợi ý đã bị GH-81/82/83 chiếm — dùng field trống kế tiếp thật sự là 24-26 (append-only, không đổi số cũ). Đánh dấu deprecated field 2-5 trong comment. Sửa comment field 9 (`confidence`) |
| `src/grpc_gen/ai_service_pb2.py`, `ai_service_pb2_grpc.py`, `*.pyi` | regenerate | `python scripts/gen_proto.py` — không sửa tay |
| `src/schemas/predict.py` | modify | Sửa comment field `confidence` (dòng 285): đúng bản chất `prediction.soh_confidence` (MC Dropout), không phải `\|IsolationForest score\|` |
| `src/schemas/prescribe.py` | modify | `PrescribeResponse`: thêm `prediction: PredictionInfo`, `anomaly: AnomalyInfo`, `risk: RiskInfo` (import từ `src.schemas.predict`, **required** — không optional, vì `run_inference()` luôn chạy đủ bất kể `enrich`); comment deprecated cho `soh_percent`/`risk_level`/`priority`/`action_code` |
| `src/services/prescription/orchestrator.py` | modify | `run_prescription()`: thêm `"prediction": prediction, "anomaly": anomaly, "risk": risk` vào dict trả về (biến đã có sẵn ở đầu hàm từ `prediction_result`, không tính toán thêm) |
| `src/grpc_server.py` | modify | `_to_prescribe_response()`: build `prediction=ai_service_pb2.PredictionInfo(...)`, `anomaly=...`, `risk=...` từ `result["prediction"]`/`["anomaly"]`/`["risk"]`, giống hệt cách `_to_predict_response()` đang làm |
| `docs/grpc-integration-be.md` | modify | Thêm đoạn ngắn (đầu file, sau bảng transport) nêu flow khuyến nghị: gọi `Prescribe` (predict chạy nội bộ, response giờ có đủ `prediction`/`anomaly`/`risk`) cho ticket/enrichment; `Predict`/`PredictStream` cho real-time monitoring dashboard |
| `tests/test_grpc_server.py` | modify | `FIXED_PRESCRIBE_RESULT`: thêm key `prediction`/`anomaly`/`risk` (dict đầy đủ, mirror `FIXED_PREDICT_RESULT`). `test_prescribe_parity_with_rest`: mở rộng assert nested `prediction.soh_percent`/`is_borderline`/`stage_confidence`/`anomaly.anomaly_status`/`risk.reasons` khớp REST |
| `tests/test_prescription.py` | modify | Thêm 1 test mới: `run_prescription()` với `run_inference` fake trả `is_borderline=True, stage_confidence=0.65` → assert `out["prediction"]["is_borderline"] is True` và `out["prediction"]["stage_confidence"] == 0.65` (forward nguyên vẹn, không tính lại) |
| `tests/test_grpc_contract.py` | không sửa | `PARITY_CASES` đã parametrize `PrescribeResponse` vs `pb.PrescribeResponse` — test `test_field_names_match_pydantic` tự động cover field-name parity cho 3 field mới, không cần thêm case |

## Approach
- `run_inference()` (đã chạy ở bước 1 của `run_prescription()`, không phụ thuộc `enrich`) đã trả đủ `prediction`/`anomaly`/`risk` dict khớp 100% shape `PredictionInfo`/`AnomalyInfo`/`RiskInfo` — bằng chứng: `/predict` endpoint dùng chính dict này để build `PredictResponse` thành công hôm nay. Vì vậy chỉ cần **forward nguyên dict**, không tính toán/transform gì thêm → không thêm forward pass, không đổi latency.
- Tái dùng 100% message proto `PredictionInfo`/`AnomalyInfo`/`RiskInfo` sẵn có (đúng đề xuất của issue) — proto chỉ thêm 3 field tham chiếu message cũ, field number 24/25/26 (append sau `prescription_id = 23`, field 19-21 issue nêu đã bị chiếm bởi các field merge sau khi issue được viết).
- REST: `response_model=PrescribeResponse` tự validate/serialize khi `orchestrator.run_prescription()` trả dict có key `prediction`/`anomaly`/`risk` — không cần sửa `src/routers/prescribe.py`.
- gRPC: `_to_prescribe_response()` build thủ công 3 sub-message (pattern giống hệt `_to_predict_response()` dòng 82-106 của `grpc_server.py`) — không extract helper dùng chung để tránh động vào code Predict đang ổn định (Surgical Changes).
- Test parity dựa hoàn toàn vào cơ chế đã có (`PARITY_CASES` cho field name, `test_prescribe_parity_with_rest` cho value) — chỉ mở rộng, không viết cơ chế mới.

## Edge Cases
- `enrich=false` (rule-only hot-path P1): `prediction`/`anomaly`/`risk` **vẫn đầy đủ** vì `run_inference()` luôn chạy ở bước 1 bất kể `enrich` — không có nhánh nào thiếu data, không cần fallback/default.
- BE cũ (gRPC) chưa biết field 24-26: proto3 forward-compatible, field lạ bị ignore, 4 flat field cũ (2-5) vẫn nguyên giá trị như trước — không breaking.
- `prediction`/`anomaly`/`risk` là field **required** trong `PrescribeResponse` Pydantic (không default) — chấp nhận được vì không có code path nào (rule-only hay enriched, blocked hay không) khiến `run_inference()` không chạy hoặc trả thiếu field.

## Acceptance Criteria
- [ ] `PrescribeResponse` (REST + gRPC) trả nested `prediction`/`anomaly`/`risk` — parity field-by-field có test
- [ ] `is_borderline`/`stage_confidence` xuất hiện trong response Prescribe
- [ ] Không thêm forward pass — latency Prescribe không đổi (<100ms benchmark, `tests/test_prescription.py::test_rule_path_under_100ms` vẫn PASS)
- [ ] Doc comment `confidence` đúng bản chất MC Dropout (proto + `schemas/predict.py`)
- [ ] Coverage ≥ 85%

## Steps
- [x] Bước 1: Sửa `protos/ai_service.proto` (3 field mới field 24-26, comment deprecated, fix comment `confidence`) → regen bằng `python scripts/gen_proto.py` — 2026-07-21
- [x] Bước 2: Sửa `src/schemas/prescribe.py` (3 field nested + comment deprecated) và `src/schemas/predict.py` (fix comment `confidence`) — 2026-07-21
- [x] Bước 3: Sửa `orchestrator.run_prescription()` — forward `prediction`/`anomaly`/`risk` dict — 2026-07-21
- [x] Bước 4: Sửa `grpc_server._to_prescribe_response()` — build 3 sub-message nested — 2026-07-21
- [x] Bước 5: Sửa `docs/grpc-integration-be.md` — flow khuyến nghị Prescribe-only — 2026-07-21
- [x] Bước 6: Cập nhật `tests/test_grpc_server.py` (`FIXED_PRESCRIBE_RESULT` + mở rộng `test_prescribe_parity_with_rest`) và thêm test mới trong `tests/test_prescription.py` — 2026-07-21
- [x] Bước 7: Chạy `pytest tests/ -v --cov=src` (≥85%) + xác nhận `test_rule_path_under_100ms` vẫn PASS — 2026-07-21 (493 passed, coverage 92%)

## Câu hỏi đã giải đáp
Không có câu hỏi cần hỏi user — toàn bộ điểm chưa rõ trong issue tự giải quyết được bằng cách đọc code:
- **Field number 24-26 thay vì 19-21 issue nêu:** đọc `protos/ai_service.proto` hiện tại thấy field 19-23 đã bị GH-81/82/83 chiếm (`blocked`, `query_gen_ms`, `generated_queries`, `prescription_id`) — issue được viết trước khi các field đó merge. Field trống kế tiếp thật sự là 24-26, vẫn giữ nguyên tinh thần "append-only" của issue.
- **Có cần tính toán lại prediction/anomaly/risk không:** không — `run_inference()` đã chạy sẵn ở bước 1 `run_prescription()` bất kể `enrich`, dict trả về khớp 100% shape đang dùng cho `/predict`. Chỉ forward, không thêm forward pass → giữ nguyên AC latency.
- **Optional vs required cho 3 field mới:** plan cũ (05-07) đề xuất optional (`| None = None`); plan này đổi thành **required** vì `run_inference()` luôn trả đủ dữ liệu ở mọi code path (rule-only, enriched, blocked) — nhất quán với cách `PredictResponse.prediction`/`anomaly`/`risk` đã required từ trước, không có lý do để Prescribe khác.
- **Test parity cho field mới:** cơ chế `PARITY_CASES` (`tests/test_grpc_contract.py`) đã parametrize `PrescribeResponse`, tự động cover field-name parity khi thêm field vào cả 2 schema — không cần test mới cho việc đó, chỉ cần mở rộng `test_prescribe_parity_with_rest` (value-level) và fixture `FIXED_PRESCRIBE_RESULT`.
- **Có extract helper dùng chung cho Predict/Prescribe không:** plan cũ đề xuất extract 3 helper function; plan này giữ nguyên duplicate mapping trong `_to_prescribe_response()` để không động vào `_to_predict_response()` đang chạy ổn định (Surgical Changes — chỉ sửa file/vùng code liên quan trực tiếp task).
