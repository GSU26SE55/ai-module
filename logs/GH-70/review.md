## BÁO CÁO CODE REVIEW — feat/GH-70-anomaly-eval-table5 — 2026-07-04
### Scope: AI
### Effort: Standard

### TÓM TẮT
Diff gồm `scripts/eval_anomaly.py` (310 dòng), `tests/test_eval_anomaly.py` (7 tests), `requirements-dev.txt` (+matplotlib), cùng 1 fix tương thích 2 dòng trong `experiment_nowcast_lobo.py` (commit của user). Code đạt mọi tiêu chí Critical: seed, không leakage, không refit scaler, hyperparameter đúng rules. F1 target không đạt là **kết quả nghiên cứu** (đã verify không phải bug), không phải lỗi code.

### PHÂN TÍCH

✅ Pass: **Reproducibility** — `np.random.seed(42)` (eval_anomaly.py:52), `IsolationForest(random_state=SEED)` (:190); import `scripts.preprocess` seed cả `random`/`np`/`torch`; matplotlib pin `==3.9.4` trong requirements-dev.
✅ Pass: **Không data leakage** — rate threshold tính từ phân bố train (:183–186); IsolationForest fit chỉ trên train X_feat (:191); threshold sweep chỉ trên val (`pick_threshold` :93–101), test chỉ dùng đánh giá cuối.
✅ Pass: **Scaler workflow** — không fit scaler mới; dùng `X_feat` đã chuẩn hóa sẵn trong `data/processed/*.pt` (cùng tensors train.py dùng), nhất quán train ↔ eval.
✅ Pass: **Hyperparameters đúng rules** — contamination=0.1, n_estimators=100, seed 42 khớp `.claude/rules/tech/ai.md`; không thêm model mới; không sửa mapping production −0.1/−0.3 trong `src/`.
✅ Pass: **Alignment guard** — replay cycle→window (`(T−30)//30+1`) có `assert` tổng windows khớp shape X_feat từng split (:176–180) — đã pass trên data thật (17456/1536/768), chống lệch nhãn thầm lặng.
✅ Pass: **Báo cáo trung thực** — Table 5 in cả số default (F1=0.000) lẫn tuned; EOL degenerate được cảnh báo runtime + ghi rõ trong table5.md; draft Section 3.5 + Limitations kèm sẵn.
✅ Pass: **Tests** — 7/7 pass, cover đủ label functions + threshold picker + edge case (spike smoothing, biên median filter); ruff check + format sạch.
✅ Pass: **Windows encoding** — output file ghi `encoding="utf-8"`; print console toàn ASCII (đã fix lỗi cp1252 gặp lúc chạy đầu).

🟡 Warning: `tests/test_eval_anomaly.py` + `logs/nckh/anomaly/*` đang **untracked** — phải `git add` trước khi `/kltn-ship 70`, nếu không PR sẽ thiếu test và số liệu.
🟡 Warning: commit `bc92b89` message "update kaggle file" không theo convention `type(#70): mô tả` và gói kèm fix ngoài scope (`experiment_nowcast_lobo.py` — unpack 3-tuple tương thích `load_cycles` GH-54, fix hợp lệ nhưng nên nêu rõ trong PR body).
🟡 Warning: `.github/workflows/ci.yml` chỉ cài `requirements.txt` nhưng chạy `ruff`/`pytest` (không có trong đó) — **gap có sẵn từ trước**, không do branch này; matplotlib nằm cùng chỗ với pytest (requirements-dev) nên mọi môi trường chạy được test đều có matplotlib. Cân nhắc issue riêng sửa CI.
🟡 Warning: eval_anomaly.py:217 — quyết định tuning dựa trên F1 đã round 4 chữ số trong `evaluate()`; vô hại ở số liệu hiện tại nhưng nếu tái dùng `pick_threshold` nơi khác nên so trên giá trị chưa round.

### RỦI RO & LƯU Ý
- **F1 target KHÔNG đạt** (rate label: tuned val 0.525 / test 0.342; documented thresholds không bao giờ kích hoạt vì score val/test ∈ [−0.075, 0.22]) — kết quả thật đã verify bằng phân bố score, cần chốt với GVHD cách frame Table 5 trước khi viết Section 4. Không phải blocker của việc ship script.
- Script là offline research tool — không đụng `src/`, không ảnh hưởng inference SLA <100ms.
- `logs/nckh/anomaly/figure_f6.*` là generated output — reproducible bằng 1 lệnh, commit để reviewer/paper dùng ngay (nhất quán tiền lệ `logs/GH-60/demo_results.json`).

### KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
(3 việc cần làm khi ship: `git add tests/test_eval_anomaly.py logs/nckh/`, PR body nêu rõ fix lobo đi kèm, và note kết quả F1 cho GVHD.)
