## BÁO CÁO CODE REVIEW — feat/GH-77-grpc-named-field-reading — 2026-07-04
### Scope: AI
### Effort: Standard

### TÓM TẮT
Đúng thiết kế đã plan — thêm field mới field-number-safe vào proto, tái dùng chính Pydantic schema (không viết logic normalize riêng cho gRPC), test parity đầy đủ cả 2 transport + PredictStream. Có 1 điểm cần lưu ý bắt buộc trước khi merge (không phải bug, nhưng ảnh hưởng thứ tự ship) — xem RỦI RO & LƯU Ý.

### PHÂN TÍCH

✅ Pass: `protos/ai_service.proto` — `reading_objects` dùng field number MỚI (3), không đổi `battery_id=1`/`readings=2`; `ReadingFields` dùng `optional` cho `cycle_count`/`soc_percent` giống pattern `PrescribeRequest.age_cycles` đã có — đúng convention wire-compatibility của dự án.

✅ Pass: `src/grpc_server.py:162-192` (`_predict_one`) — không viết hàm validate/normalize riêng cho gRPC; build `readings` thành `list[dict]` rồi đưa thẳng vào `_validate(PredictRequest, {...}, context)` y hệt luồng cũ — đúng Acceptance Criteria quan trọng nhất của issue. Dùng `HasField()` cho 2 field optional đúng cách (không dùng giá trị mặc định 0.0 để suy luận presence).

✅ Pass: Test parity không tautological — `test_predict_reading_objects_matches_readings_array`/`_6field_matches_readings_array` build từ CHÍNH `VALID_READINGS`/`VALID_READINGS_6COL` (cùng giá trị số), patch `run_inference` để bắt `call_args`, so sánh CHÍNH XÁC rows đã normalize — không chỉ so status/response shape. `test_predict_reading_objects_matches_rest_object_format` verify cross-transport (gRPC reading_objects vs REST object-format) cho cùng kết quả, không chỉ trong nội bộ 1 transport.

✅ Pass: `test_stream_accepts_reading_objects` — verify `PredictStream` (không chỉ `Predict` unary) nhận đúng `reading_objects` vì dùng chung `_predict_one()`; mix 1 request `reading_objects` + 1 request `readings` mảng trong cùng stream để chứng minh cả 2 nhánh code hoạt động song song đúng thứ tự.

✅ Pass: `test_predict_reading_objects_takes_precedence_over_readings` — verify đúng edge case đã document trong plan (gửi cả 2 field → ưu tiên `reading_objects`), không phải hành vi ngầm không test.

✅ Pass: `tests/test_grpc_contract.py::test_predict_request_fields` — sửa đúng chỗ, có comment giải thích rõ lý do loại `reading_objects` khỏi exact-match set (proto-only field, map vào Pydantic Union chứ không phải field riêng) — không làm test trở nên vô nghĩa (weakening), chỉ loại đúng 1 field có lý do chính đáng.

✅ Pass: Full suite 212 passed/0 failed, coverage 89% (`schemas/predict.py` 98%, `grpc_server.py` 91% — 8 dòng miss đều thuộc `serve()`/`__main__` entrypoint có sẵn từ trước, không liên quan code mới). Ruff check + format PASS trên toàn bộ file đã sửa/thêm.

✅ Pass: Demo `demo/grpc_predict_degraded_object_format.json` dùng lại đúng data B0048 degraded (khớp `predict_degraded_6field.json`) — không phải data giả ngẫu nhiên.

🟡 Warning (quan trọng, không phải bug — ảnh hưởng thứ tự ship): `src/schemas/predict.py` trên nhánh này chứa **y hệt** thay đổi của GH-76 (`ReadingObject` + Union type), copy thủ công vì GH-77 branch tạo từ `dev` nhưng GH-76 chưa merge. Đây là dependency thật (GH-77 không thể hoạt động nếu thiếu), đã ghi rõ trong `plan.md`, nhưng **PR của GH-77 hiện sẽ diff cả thay đổi thuộc về GH-76** nếu tạo PR bây giờ. Bắt buộc merge GH-76 vào `dev` TRƯỚC, sau đó rebase/merge `dev` vào nhánh GH-77 (nội dung `predict.py` sẽ khớp identical, không conflict thật) rồi mới `/kltn-ship 77` — nếu ship GH-77 trước, PR sẽ vô tình "authored" lại toàn bộ diff của GH-76.

🟡 Warning (nhỏ): `_predict_one()` không strict-reject khi client gửi cả `readings` và `reading_objects` cùng lúc (im lặng ưu tiên `reading_objects`) — đúng theo scope đã duyệt trong plan, nhưng nên nhắc BE rõ trong tài liệu bàn giao để tránh nhầm lẫn khi debug (gửi nhầm `readings` tưởng có tác dụng nhưng bị bỏ qua).

### RỦI RO & LƯU Ý
- **Thứ tự ship bắt buộc: GH-76 → merge dev → rebase GH-77 → ship GH-77.** Không ship GH-77 trước GH-76 trong tình trạng hiện tại.
- Code vẫn đang trên branch riêng, chưa commit/push — nhất quán với cách làm gần đây.
- `src/grpc_gen/*` đã regenerate đúng, verify `ReadingFields`/`reading_objects` xuất hiện trong `.pyi` — không cần review thủ công phần serialized bytes (auto-generated).

### KẾT LUẬN
PASS — Độ tự tin: Cao
