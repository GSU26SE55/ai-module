## BÁO CÁO CODE REVIEW — feat/GH-56-ai-extend-readings-api — 2026-07-03
### Scope: AI
### Effort: Standard

### TÓM TẮT
Thay đổi nhỏ, đúng scope plan.md: mở rộng `PredictRequest.readings` chấp nhận 6-cột (BE tự tính cycle_count/soc_percent) song song với path 3/4-cột cũ, không đổi wire format proto, không đổi router/grpc_server. Logic đúng, test parity thực sự kiểm chứng (không tautological), coverage 87%.

### PHÂN TÍCH

🟡 Warning: `src/services/inference.py:180` — `cycle_count_norm` lấy từ `raw[0, len(BASE_FEATURES)]` (dòng đầu), giả định BE luôn gửi `cycle_count` là hằng số suốt 30 dòng. Không có validation nào bắt lỗi nếu BE gửi sai (mỗi dòng 1 giá trị khác nhau) — code sẽ âm thầm dùng giá trị dòng đầu mà không cảnh báo. Đây là quyết định đã ghi rõ trong `plan.md` (Edge Cases — "không validate strict, lấy dòng đầu"), nên chấp nhận được, nhưng nên note lại trong docstring hoặc log warning nếu có thời gian ở follow-up.

🟡 Warning: `src/services/inference.py:177` — điều kiện `raw.shape[1] >= len(BASE_FEATURES) + 2` dùng `>=` thay vì `==`. Vì Pydantic validator ở tầng trên chỉ cho phép đúng {3,4,6} cột nên thực tế không thể lọt payload 7+ cột qua API công khai, nhưng hàm `_append_derived_features` cũng được gọi trực tiếp trong unit test (không qua validator) — dùng `==` sẽ rõ ràng/chặt hơn, khớp với style `< len(BASE_FEATURES)` ngay phía trên. Không phải bug, chỉ là polish nhỏ.

✅ Pass: Không đổi wire format `.proto` — xác nhận đúng vì `Reading.values` vốn là `repeated double` (độ dài tuỳ ý); comment update chỉ mang tính document, không cần chạy lại `gen_proto.py`.
✅ Pass: `_align_features()`/`_expected_feature_count()` không cần sửa — đã verify bằng test thực tế (`raw` gốc 6-cột được giữ nguyên, truyền đúng vào `_append_derived_features`), giảm scope đúng so với plan ban đầu.
✅ Pass: Backward compat — request 3/4-cột giữ nguyên hành vi cũ (test `test_legacy_model_passthrough`, `test_cycle_idx_normalized` không bị breaking).
✅ Pass: Test parity không tautological — `test_6col_matches_4col_plus_cycle_idx_when_soc_agrees` build `soc_percent` bằng đúng `compute_soc_percent()` rồi so sánh 2 đường (6-cột trực tiếp vs 4-cột+cycle_idx tính lại) → thực sự verify công thức khớp nhau.
✅ Pass: Test parity REST/gRPC (`test_predict_6col_parity_with_rest`) verify cả 2 transport parse **cùng giá trị readings** trước khi gọi `run_inference()` (check `call_args`), không chỉ so response.
✅ Pass: Router/grpc_server không đổi — đúng như plan, logic detect nằm hết trong `inference.py`.
✅ Pass: Coverage 87% (≥85% quality gate); ruff sạch trên các file thực sự sửa (4 lỗi E402 trong `inference.py` là pre-existing trên `dev`, xác nhận qua so sánh trực tiếp, không phải do diff này).
✅ Pass: Không có data leakage / không fit lại scaler — thay đổi thuần túy ở tầng đọc input, không đụng training/scaler pipeline.
✅ Pass: Demo payload (`predict_degraded_6field.json`) sinh từ data thật (B0048), không hardcode giả.

### RỦI RO & LƯU Ý
- File weight (`models/weights/scaler.pkl`, `feature_scaler.pkl`, `isolation_forest_v1.4.pkl`, `soh_mamba_v1.4.pth`) và `notebooks/kaggle_train_long.ipynb` đang có thay đổi trong working tree nhưng **không thuộc scope GH-56** (kết quả phụ của 1 job train nền chạy xong ngoài ý muốn) — cần tách riêng, không commit chung vào PR của GH-56 để tránh lẫn 2 việc không liên quan.
- 1 test flaky (`test_prescription.py::test_rule_path_under_100ms`) khi chạy full suite — không liên quan diff này (không đụng `prescription.py`), đã xác nhận pass khi chạy riêng lẻ.

### KẾT LUẬN
PASS — Độ tự tin: Cao
