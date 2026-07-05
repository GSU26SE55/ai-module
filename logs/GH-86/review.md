## BÁO CÁO CODE REVIEW — feat/GH-86-uncertainty-health-stage — 2026-07-05
### Scope: AI
### Effort: Standard

### TÓM TẮT
Diff gọn, đúng scope plan: 1 hàm quyết định mới (`classify_health_stage_probabilistic`) + wire vào
`run_inference()` + 3 field response mới trên cả REST lẫn gRPC (proto append-only). Không đụng
training/preprocessing/scaler. Không có Critical.

### PHÂN TÍCH

✅ Pass: `src/models/anomaly_detector.py:64-96` — ngưỡng 80/85/90 KHÔNG bị duplicate: mỗi MC sample
   đi qua chính `classify_health_stage()` (single source); tie-break nghiêng stage nặng (safety-first)
   deterministic qua `_STAGE_ORDER` index.
✅ Pass: `src/services/inference.py:212-217` — `health_stage` (probabilistic) là nguồn duy nhất cho cả
   `compute_risk_profile` lẫn `prescription.py:40` (đọc `prediction["health_stage"]` từ run_inference)
   → risk/prescription/predict tự nhất quán, không chỗ nào re-derive stage từ point-estimate.
✅ Pass: `src/services/inference.py:203-206` — `soh_percent` giữ mean (số liệu báo cáo không đổi);
   chỉ threshold decision chuyển sang median/distribution. Clip [0,100] cả mean lẫn median.
✅ Pass: `protos/ai_service.proto:97-102` — chỉ THÊM field number mới 10–12, không reuse/đổi số cũ
   (wire compatible); stub regen bằng `scripts/gen_proto.py` và commit vào `src/grpc_gen/`.
✅ Pass: `src/schemas/predict.py:193-196` — 3 field mới có default → backward compatible; Pydantic
   deep-copy mutable default nên `{}` an toàn.
✅ Pass: Reproducibility/Data/Scaler — không sửa train/preprocess/scaler workflow; scaler vẫn load từ
   `models/weights/*.pkl`, không fit lại. Không có data leakage (không đụng split).
✅ Pass: Latency — zero forward pass thêm (tái dùng `mc_preds` có sẵn); benchmark real-weights
   2026-07-05: Predict avg 95.0ms < 100ms → PASS, không regression so với GH-63 (88.2ms, dao động máy).
✅ Pass: Tests — 7 unit case mới (biên 80/85/90, tie-break, majority-vs-mean, clip, empty-raise),
   consistency test REST (`test_stage_probabilities_consistent`), parity gRPC mở rộng cho proto map.
   Full suite: 271 passed, coverage 89% (≥85%).

🟡 Warning: `src/services/inference.py:214` — `classification` (median-based, ngưỡng 80/90) và
   `health_stage` (bin-argmax, ngưỡng 80/85/90) có thể lệch nhau với phân phối đa modal hiếm
   (vd shares 0.4 EOL / 0.3 Maint / 0.3 Healthy → stage="End Of Life" nhưng median ~81 →
   classification="Degrading"). Hai field vốn dùng thang ngưỡng khác nhau từ trước nên đây không
   phải regression; risk đi theo health_stage nên nội bộ nhất quán. Gợi ý (ngoài scope): nếu BE cần
   2 field luôn khớp, derive classification từ cùng phân phối (map stage→classification) ở ticket sau.
🟡 Warning: `classify_health_stage_probabilistic` round shares 3 chữ số TRƯỚC argmax — với
   MC_RUNS=10 (bước 0.1) vô hại; nếu sau này MC_RUNS đổi sang số không chia hết (vd 3), tổng
   probabilities có thể là 0.999 (docstring nói "sums to 1.0"). Không ảnh hưởng argmax/tie-break.
🟡 Warning: Working tree đang lẫn WIP KHÔNG thuộc GH-86: xóa `demo/predict_*.json` (6 file),
   xóa `notebooks/kaggle_train_lobo.ipynb`, sửa `scripts/experiment_nowcast_lobo.py`,
   2 file `models/embeddings/*/length.bin`. PHẢI stage chọn lọc khi commit GH-86 — nếu lẫn vào PR
   sẽ khó review và có nguy cơ mất demo payloads ngoài ý muốn.

### RỦI RO & LƯU Ý
- Tie-break nghiêng stage nặng ⇒ case 50/50 quanh ngưỡng 80 sẽ ra "End Of Life" → risk P1. Đây là
  quyết định thiết kế có chủ ý (safety-first, đã ghi trong plan); consumer PHẢI đọc kèm
  `is_borderline` để tránh auto-escalate mù. Cần nói rõ trong PR body cho BE.
- Verify trên real weights cho thấy lỗi stage chủ yếu do BIAS regression (pred 71–79 khi thật 82.9,
  cả 10 samples < 80 → confidence=1.0 nhưng sai) — borderline flag không bắt được bias, chỉ bắt được
  phân phối vắt ngưỡng. Giảm bias thuộc GH-25 (retrain) — không phải lỗi của diff này.
- `stage_confidence` là share của MC samples, KHÔNG phải calibrated probability — chưa có đánh giá
  calibration (đã ghi nhận từ phiên trước, việc riêng).

### KẾT LUẬN
PASS — Độ tự tin: Cao
