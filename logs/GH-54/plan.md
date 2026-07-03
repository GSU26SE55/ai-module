# Plan — GH-54: Thêm cycle_count + soc_percent vào input window=30 (4→6 features)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-03
- **Issue:** #54 — https://github.com/GSU26SE55/ai-module/issues/54
- **Sprint:** Sprint 4

## Mục tiêu
Thêm 2 feature mới vào input production (window=30): `cycle_count` (thứ tự cycle discharge của pin, chuẩn hoá hằng số cố định) và `soc_percent` (State of Charge %, Coulomb counting). `INPUT_FEATURES` 4→6, retrain, giữ nhất quán tuyệt đối giữa train và inference.

## Scope
**Trong scope:**
- Window=30 production pipeline: `scripts/preprocess.py`, `src/core/config.py`, `src/features/extractor.py`, `src/services/inference.py`.
- Retrain artifact `soh_mamba_v1.4.pth` + `scaler.pkl` (giữ 4 chiều, xem Approach).

**Ngoài scope:**
- Long-seq L=4096, RUL, forecast pipelines — giữ nguyên số chiều hiện tại (6/57/57), không đụng.
- Không dùng `data/raw/nasa/data-v2` — 2 feature này derive được từ `cleaned_dataset` hiện có.
- Không đổi API contract BE→AI — BE vẫn gửi 4 cột base (voltage/current/temperature/time) như hiện tại.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/features/extractor.py` | modify | Thêm `compute_soc_percent(current, time, nominal_capacity)` — Coulomb counting **cục bộ trong 1 window** (reset mỗi window), theo pattern `compute_ic_feature`/`compute_phase_mask` đã có |
| `scripts/preprocess.py` | modify | `load_cycles()` trả thêm `cycle_idx` (vị trí sau lọc+sort discharge, đã có sẵn thứ tự — chỉ cần enumerate); `cycles_to_windows()` (nhánh `long_seq=False`): tính `cycle_count_norm` + `soc_percent_norm` **PER WINDOW** (sau khi slice, trước/độc lập với scaler 4 chiều), append thành 2 cột cuối |
| `src/core/config.py` | modify | `INPUT_FEATURES` 4→6, `MODEL_VERSION` "1.3"→"1.4", thêm `CYCLE_COUNT_NORM = 200.0`, `FEATURES` append `"cycle_count"`, `"soc_percent"` |
| `src/services/inference.py` | modify | `run_inference()`: sau `scaler.transform()` (vẫn 4 cols, KHÔNG đổi), append `cycle_count_norm` (tham số mới hoặc mặc định 0 nếu BE chưa gửi — xem Edge Cases) + `soc_percent_norm` (tính từ raw current/time có sẵn trong payload) → tensor (30,6) vào model. Sửa `_expected_feature_count()`/`_align_features()` cho đúng 6 |
| `tests/test_preprocess.py`, `tests/test_inference.py`, `tests/test_extractor.py` (tên thật xem trong repo) | modify | fixture 4→6 cột; unit test `compute_soc_percent` |

## Approach
- **cycle_count:** `load_cycles()` sau khi lọc+sort discharge theo `test_id` (đã có), lấy vị trí trong danh sách làm `cycle_idx` (0-based). Chuẩn hoá: `cycle_idx / CYCLE_COUNT_NORM` (CYCLE_COUNT_NORM=200, dựa trên cycle dài nhất quan sát được trong dataset — B0033/B0034 ~197 cycles). **Không** normalize theo tổng cycle của chính pin — ở production chưa biết trước pin thật sẽ sống bao nhiêu cycle, normalize kiểu đó không tái tạo được ngoài đời.
- **soc_percent:** Coulomb counting **cục bộ trong từng window 30 bước** — SOC=100% tại **row đầu của window đó** (không phải đầu cycle thật). Lý do đổi từ "100% đầu cycle" (lựa chọn ban đầu) sang window-local: `run_inference()`/`predict_soh_long()` ở production chỉ nhận **1 window rời rạc mỗi lần gọi**, không giữ state giữa các request (đúng pattern đang dùng cho IC-curve/phase-mask ở long-seq — stateless, tính từ chính window). Giữ "100% đầu cycle" sẽ cần thêm session-state theo từng pin (đụng vào phần dở của #12) — ngoài scope #54.
  - Công thức: `SOC(t) = 100 − (∫|I| dt từ row đầu window đến t) / NOMINAL_CAPACITY × 100`, tích phân bằng `scipy.integrate.cumulative_trapezoid`, `dt` tính từ cột `Time` (giây → giờ), clip `[0, 100]`.
  - Trade-off đã thống nhất: SOC mất ý nghĩa vật lý toàn cycle, chỉ còn là "tốc độ xả tương đối trong 30 bước" — vẫn là tín hiệu hữu ích cho model, đổi lấy tính khả thi + nhất quán train/inference tuyệt đối.
- **Không refit MinMaxScaler (`scaler.pkl`) lên 6 chiều:** cả `cycle_count_norm` và `soc_percent_norm` đã tự nhiên bị chặn trong `[0,1]` bằng công thức cố định (chia hằng số / chia 100), không phụ thuộc phân phối train → giữ nguyên `scaler.pkl` 4 chiều (base physical features) như hiện tại, chỉ **append 2 cột đã normalize sẵn SAU** `scaler.transform()`. Giảm thiểu thay đổi artifact, tránh phải fit lại MinMaxScaler trên 6 chiều.
- `extract_window_features` (57-dim spectral+statistical, dùng 3 kênh đầu voltage/current/temp) **giữ nguyên hoàn toàn** — không đụng.
- Model input cuối: `(30, 6)` = `[voltage_scaled, current_scaled, temp_scaled, time_scaled, cycle_count_norm, soc_percent_norm]`.

## Edge Cases
- Window đầu cycle (i=0 trong cycle gốc): soc bắt đầu đúng 100% — nhất quán vì luôn tính lại từ đầu MỌI window.
- Cycle ngắn hơn `WINDOW_SIZE`: đã bị lọc bởi điều kiện `n >= WINDOW_SIZE` có sẵn, không ảnh hưởng.
- `cycle_idx` vượt `CYCLE_COUNT_NORM` (200) nếu pin thật sống hơn 200 cycle: giá trị >1.0, **không clip cứng** — tránh làm sai lệch giả ở vùng EOL thật (model vẫn thấy giá trị hợp lý, ngoại suy nhẹ ngoài [0,1] chấp nhận được).
- BE hiện chưa có khái niệm "cycle thứ mấy" trong payload `/predict` — `run_inference()` cần 1 cách lấy `cycle_idx` từ request (param mới có default, hoặc tạm thời mặc định 0/None → cycle_count_norm=0 nếu BE chưa truyền). Sẽ chốt cụ thể ở bước implement dựa theo schema `/predict` hiện tại.

## Acceptance Criteria
- [x] `INPUT_FEATURES=6`, `MODEL_VERSION="1.4"`, `FEATURES` đủ 6 tên (+ `BASE_FEATURES` 4 tên cho API/scaler)
- [x] `compute_soc_percent`: current=0 → 100% ✓; I=1A/1h/nominal 2Ah → 50% (khớp tính tay, cả điểm giữa 75%) ✓; clip [0,100] ✓
- [x] `preprocess.py` chạy THẬT: train X(17456,30,6) / val (1536,30,6) / test (768,30,6) — derived columns đúng range
- [x] `run_inference()` payload 4 cột → model nhận (30,6); schema validator giữ {3,4} (sửa `schemas/predict.py` dùng BASE_FEATURES — file phát sinh ngoài plan gốc, bắt buộc để giữ contract); toàn bộ REST/gRPC test xanh
- [ ] (chờ USER retrain Kaggle) MAE<2% VÀ RMSE<3% — không hồi quy so với baseline 2.06%/2.46%
- [ ] (chờ retrain xong) Latency `/predict` <100ms — chạy `python scripts/benchmark_grpc.py --real-weights`
- [x] `pytest` 189 pass (1 flaky pre-existing 9b41269), ruff sạch trên files trong scope

## Steps
- [x] Preprocess: `compute_soc_percent` (`extractor.py`) + `load_cycles` trả 3-tuple (cycle, soh, cycle_idx) + `cycles_to_windows` append 2 cột derived per-window — 2026-07-03
- [x] Config: `INPUT_FEATURES=6`, `MODEL_VERSION="1.4"`, `CYCLE_COUNT_NORM=200.0`, `NOMINAL_CAPACITY_AH=2.0`; **tách `BASE_FEATURES` (4, API/scaler) khỏi `FEATURES` (6, model input)** — 2026-07-03
- [x] Inference: `_append_derived_features` (chỉ append khi model dim = scaler dim + 2 → legacy model pass-through), `run_inference(readings, cycle_idx=None)`, `_expected_feature_count` fallback trừ 2 cột derived — 2026-07-03
- [x] Unit test: 8 test mới (3 soc hand-calc/clip, 2 preprocess derived columns, 3 _append_derived incl. legacy pass-through) + chạy preprocess THẬT trên NASA local: X(17456,30,6), cycle_count max 0.98, SOC row đầu = 1.0 mọi window — 2026-07-03
- [ ] (Kaggle, ngoài local — USER chạy) Retrain window=30 v1.4 — xác nhận MAE/RMSE không hồi quy + latency benchmark <100ms

## Câu hỏi đã giải đáp
- **Nguồn data:** `cleaned_dataset` hiện tại đủ — KHÔNG cần `data-v2` (2 feature này derive từ data sẵn có, khác với `current_load`/`voltage_load` đã bị ablate ở #25).
- **cycle_count normalize:** chia hằng số cố định 200 — không theo tổng cycle của chính pin (infeasible ở production, pin thật chưa biết trước tuổi thọ).
- **soc_percent baseline:** ban đầu chọn "100% đầu cycle thật", sau khi phát hiện production `run_inference()` stateless (không giữ state giữa các request, giống cách IC-curve/phase-mask long-seq đang làm) → đổi thành "100% đầu MỖI WINDOW 30 bước" để đảm bảo train/inference nhất quán tuyệt đối, không cần thêm hạ tầng session-state (tránh đụng #12).
- **Scope:** chỉ window=30 production — không đụng long-seq L=4096/RUL/forecast.


## Thay đổi so với plan gốc (trong lúc implement — không đổi scope)
- **Tách `BASE_FEATURES` (4) khỏi `FEATURES` (6):** plan gốc chỉ append vào `FEATURES`, nhưng `FEATURES` đang được `preprocess_long.py` (assert len+2) và `schemas/predict.py` (validator) dùng làm "4 cột base" — nếu không tách, schema sẽ reject payload 4 cột của BE và long pipeline assert fail.
- **Files phát sinh (mechanical):** `src/schemas/predict.py` (validator {3,4} qua BASE_FEATURES), `scripts/preprocess_long.py` (unpack 3-tuple + FEATURES→BASE_FEATURES, không đổi behavior), fixtures scaler/payload 4 cột trong 5 test files + `benchmark_grpc.py`/`grpc_client_demo.py`/`create_dummy_artifacts.py`.
- **Edge case cycle_idx đã chốt:** `run_inference(readings, cycle_idx=None)` — BE chưa gửi → cycle_count_norm=0.0; append chỉ xảy ra khi model dim == scaler dim + 2 (legacy model pass-through, có test).
