# Plan — GH-95: Optimize production anomaly F1 — add degradation-rate features to IsolationForest

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-07-09
- **Issue:** #95 — https://github.com/GSU26SE55/ai-module/issues/95
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
`isolation_forest_v1.6.pkl` production hiện không đạt target F1 > 0.80 (`ai.md`) vì score chỉ nhìn 57-dim spectral feature (tĩnh, per-window), không thấy được chế độ suy thoái theo thời gian (F1 tuned 0.34–0.52 trên nhãn rate-based, xem GH-70). Thêm 1 feature "degradation residual" — lệch giữa SOH dự đoán và SOH kỳ vọng theo population fade curve tại cycle hiện tại — vào input fit IsolationForest, để bắt được tín hiệu "suy thoái nhanh hơn bình thường" mà không cần lịch sử đa-cycle.

## ⚠️ Phát hiện kỹ thuật quan trọng (đã verify trên code)
- `/predict` là **stateless, single-window** (30 timestep ≈ 1 cycle) — không có lịch sử SOH nhiều cycle của cùng 1 pin trong 1 request.
- `compute_degradation_metrics()` (`src/models/anomaly_detector.py:185`) xác nhận: với window=30, rolling-slope luôn fallback về hằng số population `DEGRADATION_RATE=0.15%/cycle` — không phân biệt được giữa các request, không dùng làm feature IsolationForest được.
- **Quyết định (đã confirm với user):** dùng residual = `soh_predicted − (100 − DEGRADATION_RATE × cycle_count)` — chỉ cần `soh_predicted` (đã có từ Mamba MC Dropout) + `cycle_count` (đã có sẵn trong payload từ GH-56, cột 5) → **không đổi BE contract, không cần state per-battery**.
- **Ràng buộc kiến trúc quan trọng:** `feat_scaled` (57-dim) hiện dùng chung cho **cả Mamba's FiLM branch (`x_feat_tensor`) lẫn IsolationForest** (`src/services/inference.py:180-213`). Residual feature **chỉ được thêm vào input của IsolationForest**, KHÔNG được đổi `feat_scaled` đưa vào Mamba (tránh phải retrain Mamba — ngoài scope, GH-95 chỉ optimize anomaly detection).

## Scope
**Trong scope:**
- Hàm tính residual (dùng chung train-fit + production inference) trong `src/features/extractor.py`
- Script fit lại IsolationForest **local, không cần Kaggle** (giống tiền lệ GH-70's `eval_anomaly.py` — sklearn fit vài giây trên CPU; Mamba KHÔNG train lại, chỉ forward-pass lấy `soh_predicted` trên train set)
- Đổi format artifact `isolation_forest*.pkl` từ bare sklearn object → dict bundle `{model, version, residual_mean, residual_std}` (theo đúng pattern `scaler.pkl`/checkpoint đã có) + thêm version assertion khi load (hiện `iso_model` là artifact DUY NHẤT không có version check — GH-95 khắc phục luôn gap này vì bắt buộc phải đổi format)
- Tách `ISO_FOREST_VERSION` khỏi `MODEL_VERSION` trong `config.py` — vì lần này chỉ đổi IsolationForest, Mamba không đổi, bump chung `MODEL_VERSION` sẽ sai ngữ nghĩa (invalidate Mamba checkpoint đang đúng)
- Cập nhật `run_inference()` để tính residual + nối vào `feat_scaled` **chỉ cho** input của `iso_model.decision_function()`
- Cập nhật `scripts/train.py` (IsolationForest section) để lần retrain Kaggle tiếp theo cũng fit đúng theo feature space mới (đồng bộ, không lệch giữa 2 nơi fit)
- Evaluate lại bằng nhãn rate-based của GH-70 (`scripts/eval_anomaly.py`'s `collect_split`/`expand_to_windows`/`rate_labels` — import lại, không viết lại logic)
- Unit test cho hàm residual + test integration `/predict` với artifact format mới
- Commit artifact `.pkl` mới vào Git (bắt buộc theo `ai.md`)

**Ngoài scope:**
- Không retrain/đổi kiến trúc Mamba, không đổi `feat_scaled` đưa vào Mamba, không đổi `MODEL_VERSION`
- Không đổi BE request contract (`cycle_count` đã có sẵn từ GH-56)
- Không thêm state per-battery trong AI module (đã loại ở vòng hỏi trước)
- Không sửa `.claude/rules/tech/ai.md` — chỉ note lại thay đổi versioning trong PR description, để user tự cập nhật rule file nếu đồng ý
- Không đảm bảo F1 > 0.80 tuyệt đối — nếu sau khi thêm feature vẫn không đạt, báo cáo trung thực (đúng tinh thần GH-70), không cố tune quá tay để "đẹp số"
- Rerun `logs/nckh/anomaly/table5.md` cho paper — việc đó thuộc GH-70, không đụng ở đây

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/features/extractor.py` | modify | thêm `compute_degradation_residual(soh_pred, raw_cycle_count) -> float`, dùng `DEGRADATION_RATE` từ `src.models.anomaly_detector` |
| `src/core/config.py` | modify | thêm `ISO_FOREST_VERSION`, đổi `ISO_FOREST_PATH` dùng version riêng thay vì `MODEL_VERSION` |
| `src/core/model_loader.py` | modify | load `iso_model` như dict bundle, thêm version assert (giống pattern scaler/Mamba) |
| `src/services/inference.py` | modify | tính residual, scale bằng `residual_mean/std` từ bundle, nối vào input `decision_function()` (KHÔNG đổi `x_feat_tensor` cho Mamba) |
| `scripts/refit_isolation_forest.py` | create | fit local: load Mamba v1.6 (forward-pass only) + reconstruct cycle_count qua `load_cycles`/`collect_split` (import từ `eval_anomaly.py`) → tính residual → fit IsolationForest 58-dim → eval P/R/F1 bằng rate-based label (import `rate_labels` từ `eval_anomaly.py`) → save bundle |
| `scripts/train.py` | modify | IsolationForest section: dùng cùng hàm residual + format bundle mới, để Kaggle retrain tiếp theo nhất quán |
| `models/weights/isolation_forest_v{ISO_FOREST_VERSION}.pkl` | create (output) | artifact mới, commit vào Git |
| `tests/test_inference.py` | modify | update test cho artifact bundle format mới (feature: 58-dim vào iso, 57-dim vào Mamba không đổi) |
| `tests/test_extractor.py` hoặc file test mới | modify/create | unit test `compute_degradation_residual()` — cycle_count=None, cycle_count=0, cycle_count lớn, residual âm/dương |

## Approach
1. `compute_degradation_residual(soh_pred, raw_cycle_count)`: nếu `raw_cycle_count is None` → return `0.0` (giống pattern `cycle_count_norm=0.0` hiện có khi thiếu cycle info); ngược lại `expected = 100.0 - DEGRADATION_RATE * raw_cycle_count`, return `soh_pred - expected`.
2. `scripts/refit_isolation_forest.py`: forward-pass Mamba (eval mode, single pass — không MC Dropout, không cần train) lấy `soh_pred` cho từng window train/val/test; dùng `collect_split`+`expand_to_windows` (import từ `eval_anomaly.py`) để có `raw_cycle_count` mỗi window; tính residual; z-score bằng mean/std **của train** (không leak val/test); nối `[feat_scaled(57), residual_scaled(1)]` = 58-dim; fit `IsolationForest(contamination=0.1, n_estimators=100, random_state=42)` trên train 58-dim; eval P/R/F1 val/test bằng `rate_labels` (đúng nhãn GH-70 đã GVHD duyệt); in kết quả so sánh trước/sau.
3. `run_inference()`: sau khi có `soh_median`/`raw_cycle_count` (đã tính sẵn trong hàm), gọi `compute_degradation_residual`, scale bằng `residual_mean/std` load từ bundle, `iso_features = np.concatenate([feat_scaled, [[residual_scaled]]], axis=1)`, `score = model_loader.iso_model["model"].decision_function(iso_features)[0]`.
4. `model_loader.py`: `iso_artifact = joblib.load(ISO_FOREST_PATH)`; assert `iso_artifact["version"] == ISO_FOREST_VERSION`; lưu `iso_model = iso_artifact` (dict) thay vì bare object.
5. Nếu F1 vẫn < 0.80 sau khi thử: báo cáo số đạt được, không tự ý đổi thêm hyperparameter/feature ngoài approach đã chốt — escalate cho user quyết định bước tiếp theo (đúng nguyên tắc GH-70).

## Edge Cases
- `raw_cycle_count is None` (payload cũ 3/4-cột, không có cycle info) → residual = 0.0 → coi như "đúng kỳ vọng trung bình", không phạt/thưởng anomaly score
- `raw_cycle_count` ngoài range `[0, CYCLE_COUNT_NORM]` (đã có warning/clip sẵn ở `_append_derived_features`) → dùng giá trị đã clip cho residual để nhất quán
- Latency: thêm 1 scalar feature — benchmark lại `scripts/benchmark_grpc.py --real-weights` để confirm vẫn <100ms (kỳ vọng không đổi đáng kể, nhưng phải verify không giả định)
- Artifact cũ (`isolation_forest_v1.6.pkl`, bare object không version) vẫn còn trên `models/weights/` sau khi đổi tên file mới theo `ISO_FOREST_VERSION` — không xoá, giữ để rollback nếu cần

## Acceptance Criteria
- [ ] `compute_degradation_residual()` có unit test đủ edge case (None, 0, giá trị lớn, âm/dương)
- [ ] `scripts/refit_isolation_forest.py` chạy local < 1 phút, seed 42, in được F1 val/test trước/sau so sánh
- [ ] F1 cải thiện rõ rệt so với baseline 0.34 (test)/0.525 (val) — nếu đạt ≥ 0.80: ghi rõ đạt target `ai.md`; nếu không đạt: báo cáo trung thực số đạt được + không tự tune quá tay
- [ ] `/predict` (REST + gRPC) vẫn trả kết quả đúng shape, không lỗi với artifact bundle mới
- [ ] Latency benchmark lại — vẫn < 100ms (`scripts/benchmark_grpc.py --real-weights`)
- [ ] Mamba's `x_feat_tensor` không đổi (vẫn 57-dim) — verify bằng test rằng SOH prediction không đổi so với trước khi thêm residual feature
- [ ] `isolation_forest_v{ISO_FOREST_VERSION}.pkl` commit vào Git
- [ ] `pytest tests/ --cov=src` ≥ 85%, PASS

## Steps (AI)
- [ ] Bước 1: Viết `compute_degradation_residual()` trong `src/features/extractor.py` + unit test
- [ ] Bước 2: Đổi `config.py` (`ISO_FOREST_VERSION`) + `model_loader.py` (bundle format + version assert)
- [ ] Bước 3: Viết `scripts/refit_isolation_forest.py` — fit + eval local, so sánh F1 trước/sau
- [ ] Bước 4: Chạy script, xem kết quả F1 — nếu có vấn đề bất ngờ (residual không tách được nhãn) → dừng, báo cáo lại trước khi tiếp tục
- [ ] Bước 5: Cập nhật `run_inference()` dùng artifact + residual mới
- [ ] Bước 6: Đồng bộ `scripts/train.py` IsolationForest section (Kaggle retrain sau này nhất quán)
- [ ] Bước 7: Update `tests/test_inference.py` + benchmark latency lại
- [ ] Bước 8: `pytest tests/ --cov=src` full suite PASS ≥ 85%

## Câu hỏi đã giải đáp
1. **Tách issue riêng hay dùng chung GH-70?** → Tạo issue mới (GH-95) — GH-70 giữ scope paper/Table 5, GH-95 scope production.
2. **Cách tính degradation-rate feature khi inference stateless single-window?** → Residual từ population fade curve (`soh_predicted − expected_soh_tại_cycle`), dùng `cycle_count` đã có sẵn trong payload (GH-56) — không đổi BE contract, không cần state per-battery.
3. **`feat_scaled` dùng chung cho Mamba + IsolationForest — có đổi cả 2 không?** → Không. Chỉ IsolationForest nhận thêm residual feature (58-dim); Mamba giữ nguyên 57-dim, tránh phải retrain Mamba.
4. **Versioning artifact mới?** → Tách `ISO_FOREST_VERSION` khỏi `MODEL_VERSION` (quyết định tự đưa ra, sẽ nêu rõ khi approve plan) vì Mamba không đổi trong task này, bump chung version sẽ sai ngữ nghĩa.
