# Plan — GH-43: Warmup stages tuỳ biến qua CLI (--warmup-stages)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-03
- **Issue:** #43 — https://github.com/GSU26SE55/ai-module/issues/43
- **Sprint:** Sprint 4

## Mục tiêu
Cho phép chọn warmup stages qua CLI để ablation warmup ngắn (2-stage `2048,4096`) vs mặc định 5-stage (`256,512,1024,2048,4096`). Kỳ vọng 2-stage nhanh hơn ~50-60% mà accuracy không hồi quy (bỏ L=256 chỉ chứa 6% context của cửa sổ 4096).

## Scope
**Trong scope:**
- Thêm CLI `--warmup-stages` (chuỗi phân tách dấu phẩy, vd `2048,4096`) → parse `list[int]` → truyền vào `train_long(stages=...)`.
- Giữ **default 5-stage** (`WARMUP_STAGES` không đổi) — flag opt-in để ablation.

**Ngoài scope:**
- KHÔNG đổi `WARMUP_STAGES` trong config (tránh âm thầm đổi baseline các run khác).
- KHÔNG đổi logic warmup của `train_long` (đã sẵn: append `seq_len` nếu thiếu, lọc stage ≤ seq_len).
- KHÔNG đụng `train()` window=30, RUL.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/train.py` | modify | argparse `--warmup-stages` (parse comma→list[int]) + truyền `stages=args.warmup_stages` vào `train_long(...)` (None nếu không truyền → giữ WARMUP_STAGES) |

## Approach
- `train_long` đã có param `stages: list[int] | None = None` và dòng `base = stages if stages is not None else WARMUP_STAGES` + tự append `seq_len` + lọc `s <= seq_len` → **không cần đụng thân hàm**, chỉ cần đường CLI.
- argparse: `--warmup-stages "2048,4096"` → `[int(s) for s in v.split(",")]`; default `None`.
- Ablation Kaggle: chạy 2 lần cùng config, chỉ khác `--warmup-stages` (bỏ trống = 5-stage baseline vs `2048,4096`).

## Edge Cases
- Không truyền flag → `None` → dùng `WARMUP_STAGES` (5-stage) — hành vi cũ y nguyên.
- Stage > seq_len → `train_long` đã lọc bỏ; stage cuối luôn = seq_len (đã append).
- Chuỗi rỗng/không hợp lệ → argparse type function raise lỗi rõ ràng (validate int).
- `--warmup-stages 4096` (1 phần tử = chỉ final, không warmup) → hợp lệ, train thẳng L=4096.

## Acceptance Criteria
- [x] `--warmup-stages 2048,4096` → forward đúng `stages=[2048, 4096]` vào train_long (test mock verify); log "Warmup stages" từ logic sẵn có (smoke chạy thật với stages custom).
- [x] Không truyền flag → `stages=None` → WARMUP_STAGES 5-stage (test verify) — baseline y nguyên.
- [x] `pytest tests/test_train_long.py` 7/7 PASS; full suite 181 pass; ruff sạch.
- [x] `train()` window=30 + RUL không đụng — diff chỉ argparse/main + tests.
- [ ] (Kaggle — chờ USER chạy sau khi merge) ablation 5-stage vs `2048,4096`: đo wall-clock (target ~50-60% nhanh hơn) + MAE/RMSE B0048 không hồi quy (<0.1% MAE).

## Steps
- [x] Model/training: thêm `_parse_warmup_stages` + argparse `--warmup-stages` + truyền `stages=args.warmup_stages` vào `train_long(...)` — 2026-07-03
- [x] Unit test: 4 test mới (parse valid/invalid, CLI forward stages, default giữ None→5-stage); smoke CPU đã có sẵn (`test_train_long_smoke` stages=[16,32]); `pytest tests/test_train_long.py` 7/7 PASS — 2026-07-03
- [ ] (Kaggle, ngoài local — USER chạy) ablation 5-stage vs `--warmup-stages 2048,4096` → ghi speedup + MAE/RMSE vào issue #43

## Câu hỏi đã giải đáp
- **Scope (đã hỏi):** thêm flag `--warmup-stages`, GIỮ default 5-stage — ablation sạch, không đổi baseline (đúng pattern #34/#35/#37/#38). KHÔNG hardcode đổi `WARMUP_STAGES`.
- **train_long không cần sửa thân hàm** — đã tham số hoá `stages` + tự append seq_len.
