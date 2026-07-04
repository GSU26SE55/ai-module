# Plan — GH-66 (+GH-65): Input range validation + OOD guard + pack-to-cell voltage normalization

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-04
- **Issue:** #66 — https://github.com/GSU26SE55/ai-module/issues/66
- **Issue gộp:** #65 — https://github.com/GSU26SE55/ai-module/issues/65 (user quyết định gộp 2 issue vào 1 branch — 2 issue phụ thuộc chặt: GH-66 yêu cầu validate SAU pack-to-cell normalization của GH-65)
- **Sprint:** Sprint 4 (due 2026-07-11)
- **Branch:** `feat/GH-65-pack-to-cell-ood-guard` — PR body sẽ có `Closes #65` + `Closes #66`

## Mục tiêu
1. **GH-65:** BE gửi reading pin 12V (pack) kèm `pack_config.n_series` → chia voltage về per-cell TRƯỚC scaler và TRƯỚC warning thresholds → SOH hợp lý, không còn báo động giả OVERVOLTAGE_CRITICAL/escalate P1.
2. **GH-66:** Reading có giá trị ngoài phân phối train (sau khi quy đổi per-cell) hoặc NaN/Inf → **reject 422** (REST) / `INVALID_ARGUMENT` (gRPC) với message rõ ràng — hết silent failure "SOH=0%, REPLACE_IMMEDIATELY" trên dữ liệu cảm biến hỏng.

## Scope
**Trong scope:**
- `pack_config: {n_series: int ≥ 1, chemistry: str}` optional trong `PredictRequest` (default n_series=1 — backward compatible)
- Quy đổi `voltage_cell = voltage_pack / n_series` trong inference, trước scaler.transform và trước anomaly warning thresholds (current/temperature giữ nguyên — pack nối tiếp)
- Khoảng hợp lệ per-cell trong `config.py`: voltage [2.0, 4.5] V · current [-5.0, 5.0] A · temperature [-10, 60] °C · soc_percent [0, 100] (theo issue #66 — phân phối NASA + margin)
- Validate giá trị trong Pydantic schema (sau quy đổi n_series) → REST/gRPC parity tự có vì gRPC dùng chung schema
- Chặn NaN/Inf trong mọi cột readings
- gRPC contract: thêm message `PackConfig` + field mới vào `PredictRequest`/`PrescribeRequest`/`ResponseMetadata` (CHỈ thêm field number mới), regen stub
- Response `metadata.n_series` để trace
- **Hard reject only** (user đã chốt) — KHÔNG có tầng soft-flag `INPUT_OUT_OF_DISTRIBUTION`

**Ngoài scope:**
- Soft-flag / confidence penalty cho lệch nhẹ trong khoảng cứng (user chọn hard reject — nếu sau này cần mở issue riêng)
- Chemistry-aware normalization (LiFePO4 curve khác NMC — `chemistry` chỉ lưu làm metadata; validate accuracy pin 12V thật thuộc **GH-67**)
- Range cho cột `time` (issue không định nghĩa — chỉ check finite)
- Đổi hành vi clip `cycle_count` (GH-59 — giữ nguyên)
- Retrain model/scaler — không đụng artifacts

## Endpoints
| Method | Path | Thay đổi |
|--------|------|----------|
| POST | `/predict/` | Request thêm optional `pack_config`; 422 khi giá trị ngoài khoảng/NaN; response thêm `metadata.n_series` |
| POST | `/prescribe/` | Kế thừa như trên (PrescribeRequest extends PredictRequest) |
| gRPC | `Predict`/`PredictStream`/`Prescribe` | Field mới trong proto; `INVALID_ARGUMENT` khi vi phạm (qua chung Pydantic) |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/config.py` | modify | Thêm `VOLTAGE_CELL_RANGE`, `CURRENT_RANGE`, `TEMPERATURE_RANGE`, `SOC_RANGE` + comment cite nguồn khoảng |
| `src/schemas/predict.py` | modify | `PackConfig` model (n_series ge=1, chemistry optional); validator: NaN/Inf check + range check trên voltage/n_series, current, temp, soc |
| `src/services/inference.py` | modify | `run_inference()` nhận n_series → chia cột voltage trước scaler + trước warning thresholds; metadata thêm `n_series` |
| `src/routers/predict.py` | modify | Truyền `pack_config` xuống service (nếu signature cần) |
| `src/schemas/prescribe.py` | modify? | Chỉ nếu không kế thừa PredictRequest — kiểm tra lúc implement |
| `src/services/prescription.py` | modify | Truyền n_series qua run_inference |
| `protos/ai_service.proto` | modify | `message PackConfig{int32 n_series=1; string chemistry=2;}`; `PredictRequest.pack_config=3`; `PrescribeRequest.pack_config=7`; `ResponseMetadata.n_series=5` — chỉ THÊM số mới |
| `src/grpc_gen/*` | regen | `python scripts/gen_proto.py` |
| `src/grpc_server.py` | modify | Map pack_config proto→dict trước validate; map n_series vào ResponseMetadata |
| `tests/test_inference.py` | modify | Test pack-to-cell + metadata n_series |
| `tests/test_schemas.py` (hoặc file test schema hiện có) | modify/create | Range per-field → 422; NaN/Inf → 422; biên [2.0, 4.5] → pass; 12V không pack_config → 422 message nhắc pack_config |
| `tests/test_grpc_server.py` | modify | Parity: cùng payload vi phạm → REST 422 & gRPC INVALID_ARGUMENT; 12V+n_series=3 OK |
| `demo/predict_12v_pack_6field.json` | create | Payload demo 12V + n_series=3 (thay cho `demo/predict_oob_cycle_6field.json` trong issue — file đó KHÔNG tồn tại trong repo; AC GH-59 verify bằng unit test hiện có) |

## Approach
- **Validation đặt trong Pydantic `PredictRequest`** (model_validator after): check finite toàn bộ → lấy `n_series` (default 1) → validate `voltage/n_series` ∈ VOLTAGE_CELL_RANGE, current/temp/soc theo range — vì gRPC `_validate()` dùng chung schema nên 2 transport reject giống nhau, không viết logic 2 lần.
- **Quy đổi thật (chia voltage) đặt trong `run_inference()`** ngay đầu pipeline: `readings[:, 0] /= n_series` → mọi bước downstream (scaler, anomaly thresholds, feature_summary) tự động per-cell.
- Payload 12V **không** pack_config → n_series=1 → voltage_cell=12 > 4.5 → 422 với message: giá trị, khoảng cho phép, gợi ý "nếu là pin pack, gửi kèm pack_config.n_series" — thỏa AC của cả 2 issue bằng 1 cơ chế.
- Proto: chỉ thêm field number mới (wire compatibility), regen bằng `scripts/gen_proto.py`, commit stub.
- Latency: validation là so sánh vô hướng trên 30×6 số — không đáng kể; vẫn benchmark lại trước ship theo rule.

## Edge Cases
- Payload cũ 3/4/6 cột KHÔNG có pack_config → n_series=1, mọi behavior giữ nguyên (regression: 207 test hiện có phải pass nguyên vẹn)
- Giá trị đúng biên (2.0/4.5V, ±5A, -10/60°C, 0/100%) → PASS (inclusive)
- NaN/Inf ở bất kỳ cột nào (kể cả time) → 422
- `n_series=0` hoặc âm → 422 (Pydantic ge=1)
- `pack_config` có chemistry nhưng thiếu n_series → n_series default 1
- Legacy 3 cột (không có soc) → chỉ validate voltage/current/temp
- PredictStream: window vi phạm giữa stream → abort với INVALID_ARGUMENT sau k−1 responses (theo quy tắc bidi hiện có — test)

## Acceptance Criteria
- [ ] Payload 12V + `n_series=3` → 200, SOH hợp lý, KHÔNG có OVERVOLTAGE_CRITICAL trong warnings, `metadata.n_series=3`
- [ ] Payload 12V KHÔNG pack_config → 422, message nêu field/giá trị/khoảng + gợi ý pack_config
- [ ] Từng field ngoài khoảng → 422 với message rõ field nào; NaN/Inf → 422
- [ ] Giá trị biên → 200
- [ ] REST/gRPC parity: cùng payload vi phạm → 422 vs INVALID_ARGUMENT (test enforce)
- [ ] Payload 3/4/6 cột cũ không pack_config: behavior không đổi — full suite 207 test cũ pass
- [ ] Coverage ≥ 85%, ruff sạch trên files sửa
- [ ] Benchmark latency `--real-weights` vẫn <100ms (avg)

## Steps
- [x] Bước 1 (Config + Schema): ranges vào `config.py`; `PackConfig` + finite/range validators vào `predict.py`; `tests/test_schemas.py` mới 37 test pass — 2026-07-04
- [x] Bước 2 (Inference): chia voltage theo n_series đầu `run_inference()` (in-place trên raw → scaler/thresholds/feature_summary đều per-cell); metadata `n_series`; truyền từ router predict/prescribe + `run_prescription`. Verified TestClient: 12V+3S→200 không OVERVOLTAGE, 12V trần→422+hint, payload cũ không đổi — 2026-07-04
- [x] Bước 3 (gRPC): proto thêm `PackConfig` + `PredictRequest.pack_config=4` + `PrescribeRequest.pack_config=7` + `ResponseMetadata.n_series=5` (chỉ field number mới) → regen stub → map trong `grpc_server.py` (`_pack_config_dict`: proto3 n_series=0 → 1) — 2026-07-04
- [x] Bước 4 (Unit test): `test_schemas.py` (37), inference pack-to-cell (3), router REST (5), gRPC pack_config/parity/NaN (7). **Lưu ý:** fixture `VALID_READINGS` cũ của test_grpc_server dùng `rand()∈[0,1)` (voltage 0.37V) — bị range guard reject ĐÚNG THIẾT KẾ, đã sửa fixture sang giá trị vật lý thực [3.5, 4.1]V (dưới ngưỡng warning 4.15V); thêm `n_series: 1` vào FIXED_PREDICT_RESULT metadata — 2026-07-04
- [x] Bước 5 (Verify): full suite **263 passed, coverage 89%** ✅; ruff sạch trên files sửa (4 E402 pre-existing của inference.py giữ nguyên như GH-63) ✅; benchmark `--real-weights`: **`Predict avg 85.4ms < 100ms → RESULT: PASS`** — 2 lần đo FAIL trước đó (107-110ms) đã chứng minh là nhiễu môi trường bằng thí nghiệm stash (baseline dev code cũng 117ms cùng thời điểm, sáng cùng ngày đo 89.8ms); đo lại lúc máy bình thường → PASS. Benchmark script sửa sang input realistic (input rand[0,1) cũ bị chính OOD guard reject — bằng chứng guard hoạt động) — 2026-07-04
- [x] Bước 6 (Docs/demo): `demo/predict_12v_pack_6field.json` (voltage ~10.4V pack, n_series=3); limitation LiFePO4 → GH-67 ghi trong docstring `PackConfig` (schema) + comment proto — 2026-07-04

## Câu hỏi đã giải đáp
- **Thứ tự GH-65/GH-66:** user chọn **gộp cả 2 vào 1 ticket/branch** (lệch quy tắc "1 issue = 1 branch" — chấp nhận có chủ ý vì 2 issue phụ thuộc chặt; PR sẽ `Closes` cả 2). Branch đặt theo GH-65 (số nhỏ hơn, P1).
- **Soft-flag vs hard reject:** user chọn **chỉ hard reject 422** — không thêm tầng warning INPUT_OUT_OF_DISTRIBUTION/confidence penalty. Khoảng [2.0, 4.5]V đã có margin so với phân phối NASA (~2.5–4.2V).
- **File `demo/predict_oob_cycle_6field.json` trong issue #66 không tồn tại trong repo** — thay bằng verify GH-59 qua unit test hiện có + tạo demo payload 12V mới.
