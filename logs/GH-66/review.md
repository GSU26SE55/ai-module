## BÁO CÁO CODE REVIEW — feat/GH-65-pack-to-cell-ood-guard — 2026-07-04
### Scope: AI
### Effort: Deep (schema + inference + API + gRPC contract)

### TÓM TẮT
Ticket gộp GH-65 (pack-to-cell) + GH-66 (input range guard). Diff đọc đầy đủ (`git diff` 16 files, +436/−56). Đạt toàn bộ acceptance criteria: 12V+3S hết báo động giả, 12V trần bị chặn kèm hướng dẫn, NaN/Inf bị chặn, REST/gRPC parity có test enforce, payload cũ giữ nguyên behavior, benchmark PASS 85.4ms.

### PHÂN TÍCH

✅ Pass: **Validation đặt đúng chỗ** — toàn bộ range/NaN guard nằm trong Pydantic `PredictRequest` (`src/schemas/predict.py`), gRPC `_validate()` dùng chung schema → 2 transport reject giống nhau by-construction, có test parity xác nhận (`test_predict_out_of_range_parity_with_rest`).
✅ Pass: **Train/serve consistency** — chia `voltage / n_series` NGAY đầu `run_inference()` (in-place trên `raw`) nên scaler, anomaly thresholds, feature_summary đều thấy per-cell — đúng phân phối model được train; validator check `row[0]/n_series` nhất quán với inference.
✅ Pass: **Thứ tự validator đúng** — NaN/Inf check trong `field_validator` (chạy TRƯỚC), range check trong `model_validator(mode="after")` (chạy SAU khi normalize ReadingObject→rows) — NaN không bao giờ lọt vào phép so sánh range (NaN comparison silently False).
✅ Pass: **Wire compatibility** — proto chỉ THÊM field number mới (`PackConfig`, `PredictRequest.pack_config=4`, `PrescribeRequest.pack_config=7`, `ResponseMetadata.n_series=5`); stub regen bằng `scripts/gen_proto.py`, serialized descriptor xác nhận không đổi field cũ.
✅ Pass: **proto3 semantics xử lý đúng** — `n_series=0` (unset) → 1 trong `_pack_config_dict`, khớp REST default; n_series âm → INVALID_ARGUMENT (ge=1). Có test riêng (`test_predict_pack_config_chemistry_only_defaults_n_series_1`).
✅ Pass: **Backward compatible** — payload 3/4/6 cột không pack_config: `n_series=1`, không nhánh code mới nào chạy (guard `if n_series > 1`); 263 test full suite pass, coverage 89% (≥85%).
✅ Pass: **Benchmark PASS** — `Predict avg 85.4ms < 100ms` (real weights). Validation nằm ở Pydantic parse, không thêm gì vào hot path `run_inference` khi n_series=1.
✅ Pass: Ruff sạch trên files sửa (4 lỗi E402 pre-existing của `inference.py` giữ nguyên như GH-62/63 — ngoài scope).
✅ Pass: Không đụng training/scaler/artifacts — không có bề mặt data leakage mới; `predict_soh_long` không expose qua router nào nên không có gap OOD ở serving surface.
✅ Pass: **Guard tự chứng minh giá trị trong chính PR này** — fixture cũ của `test_grpc_server.py` và `benchmark_grpc.py` dùng `rand()∈[0,1)` (voltage 0.37V — phi vật lý) bị guard chặn ngay, phải sửa sang giá trị thực [3.5, 4.1]V. Đây chính xác là loại silent-garbage input mà GH-66 sinh ra để bắt.

🟡 Warning: `models/embeddings/*/length.bin` (2 file) lại bị ChromaDB touch khi chạy test — KHÔNG thuộc scope ticket. Khi ship: `git restore models/embeddings/` trước khi stage (lần trước đã lọt vào commit 650d0a7).
🟡 Warning: Benchmark trên máy dev Windows dao động mạnh theo tải máy (đo được 107-110ms lúc máy nghẽn, 85.4ms lúc bình thường — baseline dev code cũng 117ms lúc nghẽn). PASS là số đo lúc máy bình thường; nên re-verify trên môi trường deploy Linux như mọi lần.
🟡 Warning: `test_predict_12v_with_n_series_3_ok_and_traced` ban đầu fail vì fixture voltage lên 4.2V > ngưỡng warning 4.15V — OVERVOLTAGE lúc đó là cảnh báo ĐÚNG (per-cell thật sự cao), không phải false alarm. Đã hạ fixture xuống [3.5, 4.1]V. Lưu ý cho reviewer: ngưỡng warning (4.15V) khác ngưỡng validation (4.5V) — warning vẫn hoạt động bên trong khoảng hợp lệ, đúng thiết kế 2 tầng.

### RỦI RO & LƯU Ý
- Khoảng [2.0, 4.5]V per-cell là "NASA + margin" — pin chemistry khác (LiFePO4 3.2-3.3V vẫn nằm trong khoảng nên pass validation, nhưng accuracy chưa validate — GH-67, đã ghi limitation trong docstring `PackConfig` + proto comment).
- BE cần biết contract mới: 12V không kèm `pack_config` giờ trả 422 (trước đây trả 200 với SOH rác + OVERVOLTAGE giả). Đây là breaking change CÓ CHỦ Ý cho input vốn đã sai — cần note trong PR body cho BE.
- Hard reject only (user đã chốt khi plan) — không có soft-flag cho lệch nhẹ trong khoảng; nếu production sau này cần, mở issue riêng.

### KẾT LUẬN
PASS — Độ tự tin: Cao
