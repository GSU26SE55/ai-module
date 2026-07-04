# Plan — GH-77: Accept named-field ReadingFields in gRPC Predict (GH-76 parity for gRPC)

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-04
- **Issue:** #77 — https://github.com/GSU26SE55/ai-module/issues/77
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
GH-76 thêm format object (named-field) cho REST `/predict`. gRPC hiện không hỗ trợ được vì `Reading.values` là `repeated double` (protobuf strongly-typed, không có object tùy ý). Thêm message `.proto` mới (`ReadingFields`) + field mới trong `PredictRequest` cho named-field, tái dùng CHÍNH Pydantic schema REST để validate/normalize (không viết logic riêng) — giữ nguyên contract cũ 100%.

## Scope
**Trong scope:**
- Thêm message `ReadingFields` (6 field: `voltage`, `current`, `temperature`, `time` bắt buộc; `cycle_count`, `soc_percent` optional dùng `optional` keyword proto3) trong `protos/ai_service.proto`
- Thêm field `repeated ReadingFields reading_objects = 3;` vào `PredictRequest` (field number MỚI, không đổi `battery_id=1`/`readings=2`)
- Regenerate stub qua `python scripts/gen_proto.py`, commit `src/grpc_gen/`
- Sửa `AiServiceServicer._predict_one()` (`src/grpc_server.py`) — dùng CHUNG cho cả `Predict` (unary) và `PredictStream` (streaming) nên chỉ cần sửa 1 chỗ: nếu `request.reading_objects` không rỗng → build `readings` thành `list[dict]` (dùng `HasField()` cho 2 field optional, giống pattern đã có ở `PrescribeRequest.age_cycles`) → đưa vào `_validate(PredictRequest, {...}, context)` y hệt luồng cũ
- Test parity: gRPC `reading_objects` / gRPC `readings` (mảng) / REST object-format — cùng input logic cho cùng kết quả
- Demo: thêm 1-2 file `demo/grpc_predict_*_object_format.json` mẫu (chỉ để tham khảo cấu trúc, không cần script tự động hoá)

**Ngoài scope:**
- Không đổi `Reading`/field 1,2 hiện có
- Không đổi REST (`src/schemas/predict.py` đã đúng từ GH-76, dùng nguyên trạng)
- Không hỗ trợ legacy 3-cột ở `ReadingFields`
- Không đụng `PrescribeRequest`/`Prescribe` RPC — chỉ `PredictRequest`/`Predict`+`PredictStream`
- Không strict-reject khi client gửi CẢ 2 field (`readings` VÀ `reading_objects`) cùng lúc — ưu tiên `reading_objects` nếu có (documented edge case, không phải lỗi cần validate riêng)

## Approach
- `.proto`:
  ```protobuf
  message ReadingFields {
    double voltage = 1;
    double current = 2;
    double temperature = 3;
    double time = 4;
    optional double cycle_count = 5;
    optional double soc_percent = 6;
  }

  message PredictRequest {
    string battery_id = 1;
    repeated Reading readings = 2;
    repeated ReadingFields reading_objects = 3;  // GH-77
  }
  ```
  (proto3 `oneof` không cho phép field `repeated` bên trong nên dùng 2 field riêng, không dùng oneof)
- `_predict_one()`:
  ```python
  if request.reading_objects:
      readings = [
          {
              "voltage": r.voltage, "current": r.current,
              "temperature": r.temperature, "time": r.time,
              **({"cycle_count": r.cycle_count} if r.HasField("cycle_count") else {}),
              **({"soc_percent": r.soc_percent} if r.HasField("soc_percent") else {}),
          }
          for r in request.reading_objects
      ]
  else:
      readings = [list(r.values) for r in request.readings]
  parsed = _validate(PredictRequest, {"battery_id": request.battery_id, "readings": readings}, context)
  ```
  → `readings` (list[dict] hoặc list[list[float]]) đưa thẳng vào `PredictRequest(**payload)` — Pydantic tự phân biệt Union và normalize như REST, không cần code thêm ở `inference.py`

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `protos/ai_service.proto` | modify | Thêm `ReadingFields` message + field `reading_objects` (field number 3) |
| `src/grpc_gen/*` | regenerate | Chạy `python scripts/gen_proto.py`, commit lại |
| `src/grpc_server.py` | modify | `_predict_one()` — detect `reading_objects`, build payload dict phù hợp |
| `tests/test_grpc_server.py` | modify | Test parity: gRPC named-field / gRPC mảng / REST named-field |
| `demo/grpc_predict_degraded_object_format.json` | create | Demo mẫu (tham khảo cấu trúc proto JSON, không cần script) |
| `src/schemas/predict.py` | modify (dependency) | **Phát sinh giữa chừng:** branch GH-77 tạo từ `dev`, chưa có `ReadingObject`/Union type của GH-76 (GH-76 chưa ship/merge). Copy nguyên xi thay đổi đã review PASS của GH-76 vào đây để gRPC named-field có schema normalize dùng chung. Khi GH-76 merge vào `dev` trước, rebase/merge GH-77 sau sẽ khớp identical (không conflict thật). Nếu GH-76 đổi trước khi merge, cần re-sync file này. |

## Edge Cases
- Client gửi cả `readings` VÀ `reading_objects` → ưu tiên `reading_objects` (không strict-reject, documented)
- Client gửi `reading_objects` với `cycle_count` có ở 1 số dòng, không có ở dòng khác → Pydantic validator hiện có (GH-76) đã tự bắt lỗi này (consistency check), không cần code thêm ở gRPC
- `PredictStream` (bidi streaming) — mỗi message vẫn là 1 window đầy đủ, dùng chung `_predict_one()` nên tự động hỗ trợ `reading_objects` không cần sửa riêng

## Acceptance Criteria
- [x] Client gRPC gửi `reading_objects` (named-field) → predict thành công, kết quả khớp gửi qua `readings` (mảng) tương đương
- [x] Client gRPC cũ gửi `readings` (mảng) vẫn hoạt động y hệt — không regression
- [x] `battery_id=1`, `readings=2` không đổi field number — chỉ thêm field 3
- [x] `grpc_server.py` gọi `_validate(PredictRequest, ...)` như cũ, không viết hàm normalize riêng cho gRPC (verify bằng code review — không có logic derive/validate cycle_count/soc_percent trùng lặp trong `grpc_server.py`)
- [x] `PredictStream` cũng nhận được `reading_objects` đúng (test riêng, không chỉ `Predict` unary)
- [x] Full suite pass, coverage ≥85%, không regression — 212 passed, coverage 89%

## Steps
- [x] Bước 1 (Proto): thêm `ReadingFields` message + field `reading_objects` trong `protos/ai_service.proto` — 2026-07-04
- [x] Bước 2 (Proto): chạy `python scripts/gen_proto.py`, verify stub mới sinh đúng, commit `src/grpc_gen/` — 2026-07-04, verify `ReadingFields`/`reading_objects` xuất hiện đúng trong `ai_service_pb2.pyi`
- [x] Bước 3 (gRPC server): sửa `_predict_one()` trong `src/grpc_server.py` — 2026-07-04
- [x] Bước 4 (Unit test): test parity gRPC named-field / gRPC mảng / REST named-field trong `tests/test_grpc_server.py` — 2026-07-04, 4 test (4-field, 6-field, REST parity, precedence khi gửi cả 2 field)
- [x] Bước 5 (Unit test): test `PredictStream` với `reading_objects` — 2026-07-04, `test_stream_accepts_reading_objects`
- [x] Bước 6 (Demo): tạo `demo/grpc_predict_degraded_object_format.json` — 2026-07-04, dùng lại data B0048 degraded (giống `predict_degraded_6field.json`)
- [x] Bước 7: chạy full suite + ruff, xác nhận không regression — 2026-07-04, 212 passed, coverage 89%, ruff check + format PASS trên các file đã sửa. Có 1 test phụ thuộc (`test_grpc_contract.py::test_predict_request_fields`) cần cập nhật vì `reading_objects` là proto-only field, không map 1-1 sang Pydantic — đã sửa để exclude field này khỏi exact-match set (comment giải thích lý do)

## Câu hỏi đã giải đáp
- Không cần hỏi thêm — đã tự verify đủ qua đọc code (`_validate()` reuse Pydantic, `HasField()` pattern có sẵn, `grpc_tools` khả dụng để regenerate stub) trước khi viết plan.
