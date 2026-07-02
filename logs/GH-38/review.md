## BÁO CÁO CODE REVIEW — feat/GH-38-cawr-warmup — 2026-07-02
### Scope: AI
### Effort: Standard

### TÓM TẮT
Đổi scheduler warmup của `train_long()` từ `ReduceLROnPlateau` → `CosineAnnealingWarmRestarts` (GH-38). Thay đổi khu trú, đúng scope, correctness ổn. Không có Critical. PASS về mặt code; kiểm chứng "không hồi quy MAE/RMSE" phụ thuộc run Kaggle GPU (acceptance còn mở).

### PHÂN TÍCH
✅ Pass: Scope đúng — chỉ warmup `train_long()`. `train()` window=30 GIỮ `ReduceLROnPlateau`; final-stage CAWR (`--cosine-t0`) nguyên vẹn; RUL/forecast/lobo không đụng.
✅ Pass: Correctness — scheduler tạo 1 lần trước vòng warmup, `T_0=stage_epochs, T_mult=1`; mỗi warmup stage chạy đúng `stage_epochs` epoch (không early-stop ở warmup) → mốc restart CAWR trùng biên stage → LR reset về full đầu mỗi stage (đúng ý đồ issue).
✅ Pass: `scheduler.step()` bỏ `val_loss` — đúng cho CAWR (step theo epoch). `val_loss` vẫn được dùng cho best_state/SWA tracking + early-stop final.
✅ Pass: `eta_min` không rò rỉ — warmup 1e-6; final stage explicit `pg["lr"]=LR` + build CAWR riêng (eta_min 1e-5) trước khi step.
✅ Pass: `ReduceLROnPlateau` vẫn được `train()`/RUL/lobo dùng → import không dangling.
✅ Pass: Reproducibility — seed 42, benchmark off (deterministic) không đổi.
✅ Pass: Data/scaler/model architecture — không đụng (không rủi ro leakage/scaler).
✅ Pass: Provenance — checkpoint lưu `scheduler_warmup`, `warmup_cosine_t0`; CLI `--warmup-cosine-t0` + truyền vào call đầy đủ.
🟡 Warning: `scripts/train.py` (warmup CAWR) — nếu user set `--warmup-cosine-t0` ≠ `stage_epochs`, mốc restart KHÔNG còn trùng biên stage (restart giữa/xuyên stage). Có chủ đích (override), đã ghi help; lưu ý khi ablation.
🟡 Warning: `--stage-epochs 1` → `T_0=1`, CAWR restart mỗi epoch (LR dao động mạnh). Chỉ nên dùng cho smoke; run thật khuyến nghị `stage_epochs ≥ 3` (đã ghi trong plan Edge Cases).

### RỦI RO & LƯU Ý
- **Acceptance cuối chưa verify:** "MAE/RMSE trên B0048 không hồi quy vs ReduceLROnPlateau-warmup" là thay đổi training dynamics → phải chạy **Kaggle GPU ablation** (cùng config, chỉ toggle warmup scheduler). Đây là điều kiện PASS cuối, ngoài phạm vi review tĩnh + pytest.
- 13 lỗi ruff `E702` (semicolon) ở `_lobo`/`train_forecast_delta` là **có sẵn**, không thuộc diff này.
- Working tree còn file rác không thuộc #38 (`models/embeddings/*.bin`, `test_prediction_local.py`, `logs/GH-35/`) — KHÔNG stage khi ship.

### KẾT LUẬN
PASS — Độ tự tin: Cao (về code correctness). Kiểm chứng empirical không-hồi-quy để dành cho Kaggle ablation ở bước train/ship.
