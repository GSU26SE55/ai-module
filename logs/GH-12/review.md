## BÁO CÁO CODE REVIEW — feat/GH-12-realtime-variable-length-serving — 2026-06-16
### Scope: AI
### Effort: Standard (serving change, 2 file core + test)

### TÓM TẮT
`/predict` nhận buffer ≥30..≤10000. **Bản review đầu (PASS) đã SAI** — bỏ sót 1 Critical chỉ lộ khi
test trên data pin thật: x_feat tính sai window → SOH sai ~70%. Đã FIX + verify lại trên data thật
(sai 1.53%). Bản này phản ánh sau fix.

### 🔴 Critical — ĐÃ PHÁT HIỆN & FIX (2026-06-16)
- `run_inference`: model đạt 0.61% **chỉ khi** x_feat (FFT 54-dim) tính trên **NGUYÊN chu kỳ** (~200-800 pts) như lúc train. Bản đầu (cả GH-12 lẫn code cũ) tính x_feat trên **30 token** → lệch phân phối → SOH sai nặng (verify data thật: true 76% → pred 7%). **Bug có sẵn** (test cũ dùng dummy model nên không bắt được).
- **Fix:** `raw_feat = extract_window_features(x_scaled[:, :3])` trên **full buffer** (Mamba vẫn last-30). Verify lại: 3 cycle thật sai 0.6–2% (avg 1.53%). Guard: test `test_features_computed_on_full_buffer`.

### PHÂN TÍCH

✅ **Pass**
- **Không retrain / không đổi model:** reuse `v1.1`, chỉ window-hoá input → SOH giữ đúng phân phối train (0.61%). Đã demo thật: input 4096 và 30 ra SOH **giống hệt**, 87.7ms <100ms.
- **Scaler workflow:** dùng `model_loader.scaler`/`feature_scaler` đã load, KHÔNG refit. `x_scaled[-WINDOW_SIZE:]` đúng (scale per-timestep nên cắt sau scale = cắt trước scale).
- **Backward-compat:** input đúng 30 → `x_scaled[-30:]` == cả mảng → hành vi y hệt cũ. Regression test 30-input pass nguyên.
- **Validation:** `len < WINDOW_SIZE` reject (message vẫn chứa "30 timesteps" → test cũ pass); feature-count 3/6 giữ nguyên.
- **Phân tách đúng:** SOH ← last-30; trend/RUL/warnings/summary ← full `raw` (degradation metrics vốn chính xác hơn khi L≥500). Token dài được tận dụng, không phí.
- **Test:** `SOH(buffer)==SOH(last-30)` (seed-controlled), nhận 120 token (router), latency 4096-buffer test, coverage 92%.

🟡 **Warning**
- ~~`validate_readings_shape` không có cận trên~~ → **ĐÃ FIX (2026-06-16):** thêm `MAX_READINGS=10000` trong config + check `len(v) > MAX_READINGS` → 422; test `test_predict_rejects_oversized_buffer`.
- (nhỏ) `metadata.window_size` vẫn trả 30 — không phản ánh độ dài buffer nhận. Không sai (đây là model window), nhưng có thể thêm field `input_length` nếu BE cần biết. Optional.

### RỦI RO & LƯU Ý
- Phần non-model (scale + degradation) latency tăng tuyến tính theo độ dài buffer; model luôn ~5ms. Với buffer hợp lý (≤vài nghìn) vẫn <100ms (4096 = 87ms). Buffer khổng lồ mới đáng lo → xem Warning cap.
- Không verify trên data pin thật ở review này, nhưng SOH = path 30-token hiện có (đã 0.61%) → không cần re-verify accuracy.
- 2 test pre-existing fail (extractor / load_split) ngoài scope, không phải regression GH-12.

### RỦI RO BỔ SUNG (từ điều tra data thật)
- ⚠️ **Latency ~220ms > 100ms SLA** (MC-dropout 20 lần + FFT full cycle). Cần tối ưu sau (giảm MC_RUNS / tính feature 1 lần). Follow-up, không block functional.
- ⚠️ Buffer NÊN ≈ 1 discharge cycle (~200-800 token) để x_feat khớp train. Buffer đa-cycle (vài nghìn) có thể lệch features — cần thêm guidance/test cho BE.
- **Hệ quả production:** hợp đồng `/predict` cũ (đúng 30 token) **đã cho SOH sai** — BE phải gửi nguyên cycle. Đây là thay đổi contract cần báo BE.

### KẾT LUẬN
**PASS (sau fix)** — Độ tự tin: **Trung bình**
(Critical đã fix + verify trên data thật (1.53%). Còn rủi ro latency >100ms + buffer-length guidance
cần xử lý trước khi BE tích hợp thật. Bài học: test accuracy bằng MODEL THẬT, không chỉ dummy.)
