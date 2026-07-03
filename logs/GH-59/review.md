## BÁO CÁO CODE REVIEW — dev (GH-59, commit trực tiếp không qua branch) — 2026-07-03
### Scope: AI
### Effort: Standard

### TÓM TẮT
Fix đúng theo plan đã approve (clip `[0,1]` + log warning ở cả `preprocess.py`/`inference.py`, cả 2 nhánh của `_append_derived_features`). Logic clip + điều kiện log đã verify đúng qua test thực tế, không phải suy luận. Không có Critical.

### PHÂN TÍCH

🟡 Warning: `src/services/inference.py` — điều kiện log warning `not (0 <= raw_cycle_count <= CYCLE_COUNT_NORM)` trigger cho **cả 2 chiều** (âm lẫn vượt ngưỡng trên), nhưng `plan.md` (Edge Cases) ghi rõ "không log warning riêng cho case âm — out of scope". Code hiện tại rộng hơn plan mô tả (log cho cả 2 chiều) — không phải bug (thêm visibility cho input âm cũng hợp lý, BE gửi cycle_count âm là lỗi thật sự đáng biết), nhưng nên cập nhật lại `plan.md`/issue để khớp với hành vi thực tế, tránh gây hiểu nhầm khi review sau này. Test `test_cycle_count_norm_clipped_negative` cũng không assert `caplog` nên không phát hiện lệch này khi viết test.

✅ Pass: Điều kiện `if raw_cycle_count is not None` đảm bảo path legacy (`cycle_idx=None`, BE chưa gửi) không bị log warning sai — verify bằng test `test_cycle_count_norm_at_boundary_no_warning` (`caplog.text == ""`).
✅ Pass: Boundary `cycle_count == CYCLE_COUNT_NORM` (200) không bị coi là vượt ngưỡng (điều kiện `<=`, không phải `<`), khớp đúng ý đồ trong plan.
✅ Pass: Clip áp dụng nhất quán cả 2 nhánh (`_append_derived_features` 6-cột BE-supplied và derive server-side `cycle_idx`), test `test_6col_payload_cycle_count_clipped` verify riêng path 6-cột.
✅ Pass: `scripts/preprocess.py` clip đặt đúng vị trí (ngoài `if long_seq/else`, áp dụng chung), không thay đổi hành vi cho data NASA hiện có (`test_not_clipped_within_range` xác nhận giá trị trong range không bị đụng tới) — xác nhận đúng là no-op cho training data thật (max cycle_idx quan sát ~197 < 200).
✅ Pass: Không cần bump thêm `MODEL_VERSION`/`FEATURE_SCALER_VERSION` (đã bump ở GH-58, 1.5/1.4) — fix này không đổi giá trị training data (đã verify no-op), chỉ ảnh hưởng input ngoài phân phối lúc serving; đúng dự định gộp train chung 1 lần với GH-58.
✅ Pass: Test không tautological — dùng giá trị cụ thể ngoài range (5000, -1) và trong range (50, 200 đúng biên), so sánh cả output value lẫn log message.
✅ Pass: Full suite 202 passed / 1 flaky (không liên quan, đã xác nhận nhiều lần ở các ticket trước). Ruff sạch (chỉ lỗi pre-existing đã biết).

### RỦI RO & LƯU Ý
- Nên cập nhật `logs/GH-59/plan.md` phần Edge Cases cho khớp hành vi thực tế (log cả 2 chiều, không chỉ chiều vượt ngưỡng trên) — việc nhỏ, không blocking.
- Code vẫn commit trực tiếp lên `dev`, không qua branch/PR — ghi nhận, không thể chặn ngược ở bước review này.

### KẾT LUẬN
PASS — Độ tự tin: Cao
