# Plan — GH-34: Tăng SSM state dimension d_state 16→32 (long-seq only)

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-02
- **Issue:** #34 — https://github.com/GSU26SE55/ai-module/issues/34
- **Sprint:** Sprint 4

## Mục tiêu
Tăng SSM state của `MambaBlock` từ **d_state=16 → 32 CHỈ cho model long-seq (L=4096)** để bắt long-range degradation tốt hơn. Giữ nguyên **d_model=64**. Production window=30 + RUL **giữ 16** (không đổi hành vi/artifact đang serve).

## Scope
**Trong scope:**
- Thêm `LONG_D_STATE = 32` vào `config.py` (hằng số riêng, độc lập global `D_STATE`).
- `train_long()` dùng `LONG_D_STATE` cho long model + flag `--long-d-state` (default `LONG_D_STATE`) để ablation 16 vs 32.
- Checkpoint long lưu `d_state` **thực tế** (32) — `model_loader` đã đọc từ checkpoint nên inference tự khớp.

**Ngoài scope:**
- KHÔNG đổi global `D_STATE` (production window=30 + RUL giữ 16).
- KHÔNG đổi `d_model` (giữ 64) → không đụng FiLM/attention/head dims; MHA (#37) không bị ràng buộc chia hết.
- KHÔNG bump `LONG_MODEL_VERSION` trong issue này (để lúc finalize model long, tránh version churn giữa nhiều issue song song).
- KHÔNG sửa `soh_predictor.py` (MambaBlock đã nhận `d_state` param) và `model_loader.py` (đã đọc `d_state` từ checkpoint).

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/config.py` | modify | +`LONG_D_STATE = 32` (giữ `D_STATE = 16`) |
| `scripts/train.py` | modify | import `LONG_D_STATE`; `train_long(..., d_state=LONG_D_STATE)`; model ctor `d_state=d_state` (thay `D_STATE`); checkpoint `"d_state": d_state`; argparse `--long-d-state`; truyền vào call |
| `.claude/rules/tech/ai.md` | modify | Ghi chú long-seq dùng d_state=32 (window=30 vẫn 16) |

## Approach
- MambaBlock đã tham số hoá `d_state` → chỉ cần truyền 32 vào long model; không sửa kiến trúc.
- `model_loader.load_long_model` đã `checkpoint.get("d_state", 16)` → load model 32-state tự động, không cần đổi.
- Ablation-friendly: `--long-d-state` default 32; toggle 16 để so sánh.
- Production window=30 (`train()`, model_loader.load_models) + RUL không đụng → latency <100ms production không đổi.

## Edge Cases
- d_state=32 tăng ~2× SSM state tensor ở long-seq (mem/compute cao hơn) → nếu OOM ở L=4096 GPU, giảm `--eval-batch`/`--micro-batch` (đã có flag).
- `--long-d-state` phải > 0; giá trị lạ (vd 0) → MambaBlock sẽ lỗi shape → validate ≥1.
- Nếu retrain long với d_state=32 nhưng chưa bump version: checkpoint vẫn load đúng (đọc d_state từ file), version assertion vẫn 2.1 — chấp nhận trong giai đoạn ablation.

## Acceptance Criteria
- [ ] `LONG_D_STATE=32` trong config; global `D_STATE` GIỮ 16.
- [ ] `train_long` dựng long model với d_state=32 (mặc định); `--long-d-state 16` chạy được để ablation.
- [ ] Checkpoint long lưu `d_state=32`; smoke load roundtrip OK (model_loader dựng đúng 32).
- [ ] `train()` window=30 + RUL KHÔNG đổi (vẫn d_state=16) — verify param count không đổi.
- [ ] `pytest tests/test_train_long.py` PASS.
- [ ] **Kaggle long-seq ablation d_state 16 vs 32** (cùng config khác): ghi MAE/RMSE trên B0048; chọn cấu hình tốt hơn. Latency production không cần đo lại (window=30 không đụng).

## Steps
- [x] Preprocess: không đổi (dùng data long hiện có)
- [x] Model/training: `config.LONG_D_STATE=32`; `train_long` +param `d_state` + ctor + checkpoint; import
- [x] Inference: xác nhận `model_loader` load long d_state=32 từ checkpoint (không sửa code, chỉ verify)
- [x] CLI: `--long-d-state` + truyền vào call `train_long(...)`
- [x] Unit test + smoke: parse + ruff + `pytest tests/test_train_long.py` + smoke CPU dựng d_state=32 forward + roundtrip
- [ ] (Kaggle, ngoài local) ablation 16 vs 32 → ghi vào issue/ablation

## Câu hỏi đã giải đáp
- **Scope:** CHỈ long-seq (thêm `LONG_D_STATE`), KHÔNG đổi global → production window=30 + RUL giữ 16, không vỡ artifact serve, không re-benchmark latency production.
- **Chiều tăng:** CHỈ d_state 16→32 (giữ d_model=64) — an toàn hơn, blast radius nhỏ, không đụng FiLM/attention/MHA dims.
- **Rủi ro capacity vs generalization:** bottleneck hiện là generalization (test 1 pin 4°C); 2.06% đạt khi regularization TẮT. Khuyến nghị chạy **run B đầy đủ trước**; #34 làm như 1 lever ablation độc lập, chỉ giữ nếu cải thiện B0048 (không thì bỏ để tránh overfit).
