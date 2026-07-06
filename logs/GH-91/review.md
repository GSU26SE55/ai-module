## BÁO CÁO CODE REVIEW — feat/GH-91-add-temperature-ood-flag — 2026-07-06
### Scope: AI
### Effort: Standard

### TÓM TẮT
Diff nhỏ, đúng scope plan.md: thêm tín hiệu OOD nhiệt độ (metadata + warning) cho cả REST và gRPC, không đổi SOH/anomaly logic. Toàn bộ 292 test PASS (coverage 87%), gRPC parity tự động cover field mới, latency overhead không đáng kể.

### PHÂN TÍCH

✅ Pass: Single source of truth — `temperature_domain_distance()` (`src/models/anomaly_detector.py:271-280`) dùng chung bởi cả `generate_warnings()` và `run_inference()`, tránh 2 công thức lệch nhau.

✅ Pass: Threshold/cluster lấy từ `config.py` (`TEMPERATURE_TRAIN_CLUSTERS`, `TEMPERATURE_OOD_THRESHOLD`), không hardcode số ở nhiều nơi.

✅ Pass: Consistency giữa `>` (không `>=`) ở biên — khớp style `EOL_SOH`/`TEMP_WARNING` hiện có trong codebase (`anomaly_detector.py`).

✅ Pass: `is_temperature_ood` so sánh trên giá trị **chưa round** (`temp_domain_dist > TEMPERATURE_OOD_THRESHOLD`, `inference.py:271`), chỉ round khi ghi vào metadata hiển thị (`round(temp_domain_dist, 2)`) — tránh bug "round rồi mới so ngưỡng" làm sai kết quả ở biên.

✅ Pass: gRPC parity — `PredictStream` (`grpc_server.py:265`) gọi `self._predict_one()` giống hệt `Predict` (`grpc_server.py:219`), cả hai dùng chung `_to_predict_response()` (`grpc_server.py:68-113`) nơi 2 field mới được map (dòng 112-113) → chỉ sửa 1 chỗ, tự động đúng cho cả 2 RPC, khớp yêu cầu "gRPC là production, verify kỹ nhất" trong plan.

✅ Pass: Proto field mới đánh số 6, 7 — không đổi/reuse số cũ (1-5 giữ nguyên), đúng rule wire-compatibility trong `ai.md`.

✅ Pass: Backward-compat — `ResponseMetadata.temperature_domain_distance`/`is_temperature_ood` có default (`0.0`/`False`), response cũ deserialize không lỗi.

✅ Pass: Test coverage đủ 3 tầng — unit hàm thuần (`TestTemperatureDomainDistance`), tích hợp qua `generate_warnings`/`run_inference` (`TestTempOodWarning`, `test_inference.py`), và gRPC thật không mock (`test_predict_temperature_ood_flagged_via_grpc`) + parity test tự động cover field mới qua generic loop trong `test_predict_parity_with_rest` (đã update `FIXED_PREDICT_RESULT` mock để không KeyError).

✅ Pass: Không đổi `VOLTAGE_CELL_RANGE`/`TEMPERATURE_RANGE`/schema validation GH-66 hiện có — đúng "ngoài scope" trong plan.

🟡 Warning: `temperature_domain_distance(raw[:, 2])` được gọi **2 lần** mỗi `run_inference()` — 1 lần trong `generate_warnings()`, 1 lần trực tiếp (`inference.py:227`) để set metadata. Không sai (input giống hệt → kết quả giống hệt), nhưng là duplicate compute. Đã benchmark riêng: ~11µs/call → tổng thêm ~0.02ms/request, không đáng kể so với SLA 100ms — chấp nhận được cho scope Standard, không cần refactor truyền giá trị qua tham số ngay bây giờ.

✅ Pass (fixed trong lúc review): diff ban đầu có 2 file nhị phân `models/embeddings/*/length.bin` bị đổi do chạy test RAG local (ChromaDB tự rewrite index) — không liên quan GH-91, đã revert về bản `dev` trước khi review, diff hiện tại chỉ còn 11 file đúng scope.

### RỦI RO & LƯU Ý
- Ngưỡng `TEMPERATURE_OOD_THRESHOLD = 5.0°C` là quyết định thiết kế (bán kính "vùng tin cậy" quanh mỗi cluster), không phải số liệu thống kê từ data thật — nếu sau này có nhiều false positive/negative trong thực tế, có thể cần tune lại, nhưng đã ghi rõ lý do chọn trong code comment + plan.md.
- Field mới hiện chỉ là tín hiệu thông tin (metadata + warning), **không** ảnh hưởng `risk_level`/`priority`/`recommended_action` — đúng scope "không đổi business logic hiện có". Nếu sau này muốn OOD nhiệt độ ảnh hưởng risk scoring, cần issue riêng.
- Chưa test với real v1.6 weights (đang stash cho GH-88) — đã benchmark latency bằng cách đo overhead riêng của hàm mới (~0.02ms) cộng với baseline đã đo trước đó (~55.76ms với v1.6), không risk conflict giữa 2 branch.

### KẾT LUẬN
PASS — Độ tự tin: Cao
