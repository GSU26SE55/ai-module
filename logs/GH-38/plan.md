# Plan — GH-38: Switch warmup stages to CosineAnnealingWarmRestarts

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-02
- **Issue:** #38 — https://github.com/GSU26SE55/ai-module/issues/38
- **Sprint:** Sprint 4
- **Dev:** Nguyễn Phúc Duy (SE184821)

## Mục tiêu
Thay scheduler warmup của `train_long()` từ `ReduceLROnPlateau` (đơn điệu giảm LR) sang `CosineAnnealingWarmRestarts` để mỗi warmup stage được anneal trọn vẹn + reset LR khi sang stage dài hơn → giúp thoát local minima trong không gian tham số SSM (đúng lý do final stage đã dùng CAWR). Kỳ vọng MAE/RMSE long-seq không hồi quy, hội tụ mượt hơn.

## Scope
**Trong scope:**
- CHỈ warmup stages của `train_long()` (long-seq L=4096).
- Thêm flag `--warmup-cosine-t0` (default 0 → dùng `stage_epochs`).
- Ghi metadata scheduler warmup vào checkpoint.

**Ngoài scope:**
- KHÔNG đổi `train()` (window=30 production) — giữ ReduceLROnPlateau (quyết định: tránh đổi hành vi model đang serve).
- KHÔNG đổi RUL/forecast/LOBO schedulers.
- KHÔNG đổi final-stage CAWR (đã có, giữ nguyên `--cosine-t0`).

## Approach
- **Per-stage restart bằng 1 CAWR liên tục:** tạo `CosineAnnealingWarmRestarts(optimizer, T_0=wt0, T_mult=1, eta_min=1e-6)` **trước** vòng lặp warmup, với `wt0 = warmup_cosine_t0 or stage_epochs`. Vì mỗi warmup stage chạy đúng `stage_epochs` epoch và stage chuyển sau mỗi `stage_epochs` epoch → **mốc restart của CAWR trùng đúng biên stage** (restart tại 256→512→1024→2048). Không cần reset LR thủ công.
- Đổi bước step warmup: `scheduler.step(val_loss)` → `scheduler.step()` (CAWR theo epoch, không cần val). Final stage đã là `scheduler.step()`.
- Final stage giữ nguyên: reset LR + CAWR riêng với `--cosine-t0`.
- Deterministic không đổi (không bật benchmark; seed 42 giữ nguyên).

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/train.py` | modify | (1) `train_long()` signature +`warmup_cosine_t0: int = 0`; (2) line ~405 thay ReduceLROnPlateau → CAWR warmup + log; (3) line ~482 `scheduler.step(val_loss)`→`scheduler.step()`; (4) checkpoint dict +`scheduler_warmup: "cawr"`, `warmup_cosine_t0`; (5) argparse `--warmup-cosine-t0`; (6) truyền vào `train_long(...)` trong `main()` |

## Edge Cases
- `warmup_cosine_t0=0` (default) → tự lấy `stage_epochs` (an toàn khi user đổi `--stage-epochs`).
- `stage_epochs=1` → T_0=1: CAWR restart mỗi epoch (LR dao động mạnh) — chấp nhận cho smoke test; khuyến nghị stage_epochs≥3 cho run thật.
- Nếu chỉ có 1 stage (seq_len ≤ warmup nhỏ nhất) → không có warmup, đi thẳng final: nhánh warmup không chạy, không ảnh hưởng.
- `eta_min=1e-6` warmup (thấp hơn final 1e-5) — chấp nhận vì có restart về full LR ở stage sau.

## Acceptance Criteria
- [x] Warmup dùng CosineAnnealingWarmRestarts (T_0=stage_epochs mặc định), không còn ReduceLROnPlateau ở warmup của `train_long()`.
- [x] `train()` window=30 GIỮ NGUYÊN ReduceLROnPlateau (không đổi).
- [x] Log warmup cho thấy LR anneal + reset về full LR tại mỗi biên stage.
- [x] Flag `--warmup-cosine-t0` hoạt động; default lấy stage_epochs.
- [x] Checkpoint lưu `scheduler_warmup`, `warmup_cosine_t0`.
- [ ] Kaggle retrain long-seq (L=4096): MAE/RMSE trên test B0048 KHÔNG hồi quy so với baseline (ablation vs ReduceLROnPlateau warmup, các flag khác giữ nguyên); wall-clock tương đương.
- [x] `pytest` liên quan train_long PASS (không vỡ import/logic).

## Steps
- [x] Model/training: thêm `warmup_cosine_t0` vào `train_long()`; thay scheduler warmup (line ~405) → CAWR; sửa step (line ~482) → `scheduler.step()`; log.
- [x] Checkpoint: thêm `scheduler_warmup`/`warmup_cosine_t0` vào dict lưu.
- [x] CLI: `--warmup-cosine-t0` + truyền vào call `train_long(...)`.
- [x] Verify local: parse + ruff + `pytest tests/test_train_long.py`; smoke CPU (stage-epochs nhỏ) xác nhận scheduler chạy, log LR restart tại biên stage.
- [ ] Kaggle: ablation warmup CAWR vs ReduceLROnPlateau (cùng config) → ghi MAE/RMSE.

## Câu hỏi đã giải đáp
- **Scope:** Chỉ `train_long()` warmup — KHÔNG đụng `train()` production (tránh đổi hành vi model đang serve).
- **T_0 cho warmup ngắn:** Per-stage restart, `T_0 = stage_epochs` (mặc định), thêm flag `--warmup-cosine-t0` để override. Vì stage ngắn (3–5 epoch), T_0=20 như issue gốc sẽ gần như không restart → chọn per-stage cho có tác dụng thật.
- **Acceptance model:** đo trên long-seq (L=4096) test B0048 (split hiện tại 23/2/1), không phải window=30.

## Ghi chú branch
- #37 (MHA pooling) đang uncommitted trên `feat/GH-37-mha-pooling`. Trước khi `/kltn-implement 38`: commit #37 xong rồi tạo nhánh mới `feat/GH-38-cawr-warmup` **từ dev** (1 issue = 1 branch, ablation độc lập).
