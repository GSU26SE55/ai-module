# Plan — GH-58: Fix train/serve mismatch: compute spectral features per-window in preprocess.py (not per-cycle)

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-03
- **Issue:** #58 — https://github.com/GSU26SE55/ai-module/issues/58
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
`scripts/preprocess.py` tính spectral+statistical feature (57-dim, `extract_window_features`) trên nguyên 1 cycle rồi dùng chung cho mọi window 30-step cắt ra — trong khi `run_inference()` chỉ có 1 window 30-step/request (đúng API contract) nên tính feature trên 30 timestep. Gây train/serve mismatch nghiêm trọng (đã đo: `feat_scaled` inference range `[-20.97, 2.08]` vs `X_feat` train `[-2.05, 2.94]`; model predict 100%/252% cho pin thật SOH=61.2%). Output: `preprocess.py` tính feature per-window khớp chính xác với `inference.py`, không còn train/serve skew.

## Scope
**Trong scope:**
- Sửa `scripts/preprocess.py` — tính `extract_window_features` theo từng window 30-step (đã code xong, verify local)
- Thêm regression test đảm bảo feature khác nhau giữa các window trong cùng 1 cycle (chống tái phát bug "share 1 vector/cycle")
- Regenerate `data/processed/*.pt` local để verify (không commit — đã gitignore, Kaggle tự regenerate)

**Ngoài scope:**
- Retrain model thật trên Kaggle — làm bởi user, không phải Claude (rule: không train local)
- Verify full-pipeline accuracy (MAE/RMSE/confidence/latency với model đã train) — thuộc **GH-60**
- Xử lý `cycle_count_norm` ngoài range — thuộc **GH-59** (code độc lập, khuyến nghị train chung 1 lần Kaggle với GH-58 nhưng KHÔNG chung branch/PR)
- Không đổi `src/services/inference.py` — file này đã đúng từ trước (chính là chuẩn để `preprocess.py` khớp theo)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/preprocess.py` | modify | Đã code xong: di chuyển `extract_window_features()` vào trong vòng lặp sliding-window (per-window thay vì per-cycle), áp dụng cho cả `long_seq=True/False` (dead-code path `long_seq=True` trong file này cũng sửa cho nhất quán, dù không dùng thực tế — `preprocess_long.py` mới là script long-seq thật đang dùng) |
| `tests/test_preprocess.py` | modify | Thêm test mới: 2 window khác nhau trong cùng 1 cycle phải có `X_feat` khác nhau (chống regression về per-cycle) |

## Approach
- `cycles_to_windows()`: bỏ `cycle_feat = extract_window_features(cycle_scaled[:, :3])` tính 1 lần/cycle trước vòng lặp; thay bằng tính `window_feat = extract_window_features(window[:, :3])` **bên trong** vòng lặp `for i in range(0, T - WINDOW_SIZE + 1, WINDOW_STRIDE)`, dùng đúng slice `window` (đã cắt WINDOW_SIZE) — khớp chính xác cách `run_inference()` gọi `extract_window_features(x_scaled[:, :3])` trên `x_scaled` (30, F).
- Không đổi `extract_window_features()` bản thân hàm (đã generic, nhận mọi `(T, C)` shape) — chỉ đổi CHỖ GỌI trong `preprocess.py`.
- Regenerate `data/processed/{train,val,test}.pt` local để verify shape/range hợp lý (không commit, đã gitignore) — Kaggle Part A sẽ tự regenerate lại từ code mới khi user chạy.

## Edge Cases
- Cycle ngắn hơn `WINDOW_SIZE` (30) → không có window nào được cắt (vòng lặp `range()` rỗng) → không tính feature nào — hành vi giữ nguyên như code cũ (không đổi).
- `long_seq=True` (dead-code path, `WINDOW_SIZE > 30`, không dùng trong workflow hiện tại vì `preprocess_long.py` là script thật cho long-seq) — vẫn sửa cho nhất quán logic nhưng không có test dành riêng (không ai gọi path này).

## Acceptance Criteria
- [ ] `cycles_to_windows()` tính `X_feat` theo từng window — 2 window khác nhau trong cùng 1 cycle cho ra `X_feat` khác nhau (test mới xác nhận, không còn share 1 vector)
- [ ] Toàn bộ `tests/test_preprocess.py` pass (bao gồm `TestGh54DerivedColumns` không bị regression)
- [ ] Full `pytest tests/` pass (trừ flaky `test_rule_path_under_100ms` đã biết, không liên quan)
- [ ] Code review: logic gọi `extract_window_features` trong `preprocess.py` khớp chính xác cách gọi trong `src/services/inference.py` (cùng slice `[:, :3]`, cùng nguồn dữ liệu đã scale)
- [ ] KHÔNG yêu cầu verify bằng model đã train thật (thuộc GH-60) — AC của GH-58 chỉ ở mức code + unit test

## Steps
- [x] Bước 1 (Preprocess): sửa `cycles_to_windows()` trong `scripts/preprocess.py` — tính feature per-window thay vì per-cycle — đã xong 2026-07-03 (trong phiên làm việc trước khi tạo issue)
- [x] ~~Bước 2: tạo branch `fix/GH-58-spectral-feature-window` từ `dev`~~ — **BỎ**, không còn cần thiết: user đã tự commit code fix thẳng lên `dev` (commit `924b184 "fix 57 dim"`, kèm `feature_scaler.pkl`/`scaler.pkl` regenerate) trước khi bước này chạy tới, bỏ qua branch/PR. Ghi nhận thay đổi approach — không tạo branch nữa, làm tiếp trên `dev`.
- [x] Bước 3 (Unit test): thêm test mới trong `tests/test_preprocess.py` (`TestGh58PerWindowSpectralFeatures` — 2 test: khác window → khác feature; khớp chính xác `extract_window_features` dùng trong inference) — 2026-07-03
- [x] Bước 4: chạy lại full suite — 17/17 `test_preprocess.py` pass, full suite 196 passed/1 failed (flaky `test_rule_path_under_100ms`, không liên quan), coverage 87% — 2026-07-03
- [x] Bước 5: regenerate `data/processed/*.pt` + `scaler.pkl`/`feature_scaler.pkl` — khớp y hệt bản user đã commit (924b184), xác nhận reproducible — 2026-07-03
- [x] Bước 6: ruff check — chỉ 1 lỗi F541 pre-existing tại dòng 318 (không liên quan diff của tôi) — 2026-07-03
- [x] Bước 7 (phát sinh từ code review): bump `MODEL_VERSION` 1.4→1.5 + `FEATURE_SCALER_VERSION` 1.3→1.4 trong `src/core/config.py` — vì `soh_mamba_v1.4.pth` hiện committed trên `dev` (từ trước fix, feature per-cycle cũ) đang MISMATCH với `feature_scaler.pkl` (đã regenerate sau fix, feature per-window mới); bump version để cơ chế assertion trong `model_loader.py` tự chặn được lệch version này (v1.5 chưa tồn tại → startup fail loudly thay vì âm thầm dùng weight sai). Regenerate `data/processed/*.pt` lần nữa để stamp đúng version mới. Full suite re-run: 196 passed/1 flaky, coverage 87% — 2026-07-03

## Câu hỏi đã giải đáp
- **Scope AC:** GH-58 chỉ verify code + unit test, không chờ Kaggle train xong mới merge — verify kết quả thật (demo predict, MAE/RMSE, confidence) chuyển hẳn sang GH-60. (Không có phản hồi trong 60s, chọn theo phương án khuyến nghị.)
- **Branch:** tạo branch riêng `fix/GH-58-...` từ `dev`, tách khỏi `feat/GH-56` (khác file hoàn toàn, không conflict, đúng rule 1-issue-1-branch). (Không có phản hồi trong 60s, chọn theo phương án khuyến nghị.)
