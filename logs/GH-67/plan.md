# Plan — GH-67 (bước chuẩn bị "Mức 1"): Chemistry-aware pack config cho pin LFP 12V

## Metadata
- Status: PLANNING | Role: AI | Ngày: 2026-07-20
- Issue: #67 — [AI] Validate độ chính xác model trên pin 12V thật (chemistry mismatch) + document limitation
- Ghi chú: đây là phần code "Mức 1" (config/schema) — điều kiện cần để chạy được bước validate của GH-67.
  Nếu muốn tách issue riêng (type: feat) thay vì gộp vào GH-67 (type: test) → nói tôi biết, plan không đổi nội dung.

## Mục tiêu

Pipeline /predict (REST + gRPC) hiện quy đổi được pack→cell (GH-65) nhưng **mọi ngưỡng cảnh báo
và chuẩn hóa vẫn hardcode theo cell NASA NMC 18650 2.0 Ah**. Với pin LFP 4S 12V thật:

1. **Ngưỡng điện áp sai chemistry** (`anomaly_detector.py`): LFP xả quanh 3.0–3.3 V/cell →
   `VOLTAGE_WARNING_LOW=3.2` / `VOLTAGE_CRITICAL_LOW=3.0` (chuẩn NMC) bắn cảnh báo giả liên tục;
   ngược lại sạc đầy LFP 3.65 V/cell không bao giờ chạm `4.15/4.2` → **overcharge thật bị bỏ sót**.
2. **Dòng điện không được chuẩn hóa theo dung lượng**: pack nối tiếp không chia dòng cho n_series,
   nhưng pin solar thật (vd 50 Ah) xả 10–30 A → bị `CURRENT_RANGE=(-5,5)` reject 422 ngay ở schema,
   **không thể chạy validate GH-67**. Kể cả lọt qua, ngưỡng `CURRENT_WARNING=-2A` (=1C của cell 2Ah)
   bắn OVERCURRENT giả.
3. **SOC Coulomb-counting fallback** dùng cứng `NOMINAL_CAPACITY_AH=2.0` — sai với pack thật
   (chỉ ảnh hưởng payload 3/4 cột; payload 6 cột BE gửi soc_percent sẵn không ảnh hưởng).

KHÔNG retrain, KHÔNG đổi model/scaler/artifacts — đó là "Mức 2" (sau 20/7, dataset Severson).

## Giả định (cần bạn xác nhận khi approve)

- Pin thật là **LFP (LiFePO4) 4S 12.8V** — BE sẽ gửi `pack_config = {n_series: 4, chemistry: "LFP", capacity_ah: <Ah thật>}`. Server KHÔNG hardcode gì về pin cụ thể; thiếu field nào thì rơi về behavior NASA hiện tại (backward compatible 100%).
- **Chuẩn hóa dòng theo C-rate** (analog với chia voltage cho n_series): khi có `capacity_ah`,
  `current_equiv = current × 2.0 / capacity_ah` — quy dòng pack về "dòng tương đương cell NASA 2Ah
  cùng C-rate", áp TRƯỚC scaler + range guard + ngưỡng cảnh báo. Đây là quyết định modeling mới
  (GH-65 chỉ làm voltage) — nếu bạn không muốn, bỏ mục này thì telemetry >5A sẽ vẫn bị 422.

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/models/anomaly_detector.py` | modify | Thêm `CHEMISTRY_VOLTAGE_PROFILES` {NMC (mặc định, giá trị hiện tại), LFP}; `generate_warnings(..., chemistry=None)` chọn ngưỡng voltage theo profile. Current/temp giữ nguyên (current đã chuẩn hóa C-rate ở inference) |
| `src/schemas/predict.py` | modify | `PackConfig`: thêm `capacity_ah: float \| None (gt=0)`; validator chuẩn hóa chemistry ("lifepo4"/"lfp"→"LFP", "nmc"/"lco"/"li-ion"→"NMC", khác → giữ nguyên, dùng ngưỡng NMC). `validate_reading_ranges`: check current theo giá trị đã quy C-rate; sửa hint "12V ~ 3S" → thêm ví dụ 4S LFP. `ResponseMetadata`: thêm `chemistry`, `capacity_ah` (trace) |
| `src/services/inference.py` | modify | `run_inference(..., chemistry=None, capacity_ah=None)`: (a) quy dòng C-rate in-place trên `raw` (cùng pattern chia voltage GH-65), (b) Coulomb fallback dùng `capacity_ah or NOMINAL_CAPACITY_AH`, (c) truyền chemistry vào `generate_warnings`, (d) metadata thêm `chemistry`/`capacity_ah` |
| `src/routers/predict.py` | modify | Truyền `chemistry`, `capacity_ah` từ `request.pack_config` |
| `protos/ai_service.proto` | modify | `PackConfig`: thêm `double capacity_ah = 3;` — CHỈ thêm field number mới. `ResponseMetadata`: `string chemistry = 8; double capacity_ah = 9;` |
| `src/grpc_gen/*` | regen | `python scripts/gen_proto.py` — commit stub |
| `src/grpc_server.py` | modify | `_pack_config_dict`: map `capacity_ah` (proto3 `0.0` = unset → None); truyền vào `run_inference`; map 2 field metadata mới |
| `tests/test_schemas.py` | modify | PackConfig mới: capacity_ah ≤ 0 reject; chemistry normalize; payload 12.8V/4S pass; dòng 10A + capacity_ah=50 pass range guard, 10A không capacity → 422 |
| `tests/test_inference.py` | modify | LFP profile: v_cell min 2.95V → chemistry=None bắn VOLTAGE_CRITICAL, chemistry="LFP" không bắn; v_cell max 3.7V → LFP bắn OVERVOLTAGE, NMC im lặng; Coulomb fallback dùng capacity thật; metadata trace đúng |
| `tests/test_grpc_server.py` | modify | Parity REST↔gRPC cho capacity_ah + metadata mới |

## Ngưỡng LFP đề xuất (V/cell) — cần cite khi hội đồng hỏi

| Ngưỡng | NMC (hiện tại, giữ nguyên) | LFP (mới) | Căn cứ |
|--------|---------------------------|-----------|--------|
| CRITICAL_LOW | 3.0 | 2.5 | Discharge cutoff khuyến nghị A123 ANR26650 (cell của Severson 2019 — dataset sẽ dùng cho Mức 2) |
| WARNING_LOW | 3.2 | 2.8 | Dưới plateau 3.2–3.3V, vào vùng knee cuối xả |
| WARNING_HIGH | 4.15 | 3.65 | Charge cutoff chuẩn LFP (datasheet A123/EVE/CATL đồng thuận 3.65V) |
| CRITICAL_HIGH | 4.2 | 3.8 | Trên 3.8V bắt đầu rủi ro hư hại cell LFP |

(Ghi comment citation trong code; cập nhật phụ lục B2 `ai-research-references.md` nằm ở workflow repo — việc của bạn/leader, ngoài scope repo này.)

## Ngoài scope (Mức 2 — sau 20/7)

- Retrain trên Severson LFP, artifacts v2.x-lfp, chemistry-aware artifact selection
- Không đụng model NCKH / long-seq / RUL / prescription
- Không đổi `VOLTAGE_CELL_RANGE` (2.0–4.5 đã phủ LFP per-cell), không đổi temperature guard (GH-91)

## Steps

- [x] 1. `anomaly_detector.py`: profile ngưỡng voltage theo chemistry + test đơn vị
- [x] 2. `schemas/predict.py`: PackConfig.capacity_ah + chemistry normalize + range guard C-rate + test
- [x] 3. `inference.py` + `routers/predict.py`: chuẩn hóa C-rate, Coulomb fallback, metadata trace + test
- [x] 4. proto + regen stub + `grpc_server.py` + parity test
- [x] 5. `pytest tests/ -v` full — 492 passed, coverage 92% (≥85%); benchmark gRPC PASS (transport overhead -1.4ms, ngưỡng 50ms)
- [ ] 6. Bàn giao lệnh commit/push cho bạn chạy (không tự commit)

## Kết quả

Fix nốt 2 chỗ còn dang dở từ phiên trước (code chính đã viết xong, chỉ test fixture chưa theo kịp):
1. `tests/test_grpc_server.py::FIXED_PREDICT_RESULT["metadata"]` thiếu key `chemistry`/`capacity_ah` → `run_inference` bị mock trả dict thiếu key → `KeyError` ở `grpc_server.py:119` khi build `ResponseMetadata` (lan ra 7 test: reading_objects × 4, PredictStream, parity × 2).
2. Test parity REST↔gRPC so `metadata.chemistry` chưa xử lý case proto3 không có `null` — REST trả `None`, gRPC trả sentinel `""` (đúng convention `n_series=0`="unset" đã có từ GH-65) → thêm nhánh so sánh coi `None` (REST) ≡ `""`/`0.0` (gRPC).

## Mức 2 — Retrain SOH trên Severson LFP (bổ sung 2026-07-23)

### Nguồn dữ liệu
- **Chính:** Severson et al. 2019 (Nature Energy, Q1) — LFP/graphite A123 APR18650M1A, 1.1 Ah nominal. Raw: https://data.matr.io/1/ (.mat v7.3/HDF5, 3 batch). Parser xác nhận từ code chính thức tác giả (`rdbraatz/data-driven-prediction-of-battery-cycle-life-before-capacity-degradation/BuildPkl_BatchN.ipynb`).
- **Bổ trợ (chưa dùng, để sau):** SNL/Sandia (batteryarchive.org) — đa dạng nhiệt độ/DoD/discharge-rate mà Severson thiếu (Severson chỉ 1 nhiệt độ 30°C, discharge protocol cố định). Cần user tự tải/upload Kaggle (không có mirror sẵn).
- **Đã cân nhắc, KHÔNG dùng:** Zenodo field-data 8S/24V LFP (khớp domain nhất — 24V pack thật) — loại vì 4.4TB, không có nhãn SOH per-cycle rõ ràng (cần suy ra qua Gaussian Process, khác hẳn phương pháp hiện tại), selection bias (chỉ hàng lỗi trả về), CC BY-NC. Ghi nhận làm candidate tương lai nếu có thời gian đầu tư sâu hơn.

### Đã làm
- [x] `scripts/preprocess_lfp.py` — parse Severson .mat (h5py) → window=30/6-feature, SOH target /1.1Ah, split theo battery ID (random SEED=42, override được bằng `--val-ids`/`--test-ids`), reuse nguyên `compute_soc_percent`/`extract_window_features` từ `src/features/extractor.py` (parity với inference).
- [x] `src/core/config.py` — thêm `LFP_MODEL_VERSION`, `LFP_NOMINAL_CAPACITY_AH=1.1`, `LFP_SCALER_PATH`, `LFP_FEATURE_SCALER_PATH`, `LFP_MAMBA_PATH`, `LFP_ISO_FOREST_PATH`.
- [x] `scripts/train.py` — thêm optional `mamba_path`/`iso_path`/`model_version` params vào `train()` + CLI `--mamba-out`/`--iso-out`/`--model-version` (default = giá trị cũ, KHÔNG đổi behavior khi không truyền) — bắt buộc phải có vì `train()` mặc định ghi đè thẳng `models/weights/soh_mamba_v1.6.pth` production, không có cờ này chạy LFP sẽ phá model NASA đang chạy.
- [x] `notebooks/kaggle_train_lfp.ipynb` — notebook Kaggle end-to-end: GPU check (T4 x2) → clone → deps (+h5py) → tìm dataset Severson → preprocess_lfp.py → train.py (với `--mamba-out`/`--iso-out`/`--model-version` riêng) → check target metric → đóng gói zip → dọn output.
- [x] `pytest tests/ -q` full sau khi sửa train.py/config.py — 539 passed, không có test nào fail (train() không có test riêng nhưng thay đổi chỉ thêm optional param có default giữ nguyên behavior cũ).

### Chưa làm (ngoài scope bước này)
- Chemistry-aware artifact selection trong `model_loader.py`/`inference.py` (chọn bộ LFP khi `pack_config.chemistry=="LFP"`) — cần bước/issue riêng SAU khi có checkpoint LFP thật để test.
- Augment thêm SNL dataset (nhiệt độ/DoD đa dạng) — optional, sau khi user tự tải.
- Document limitation cuối cùng (GH-67 gốc yêu cầu) — viết sau khi có số liệu MAE/RMSE thật từ Kaggle.

`pytest tests/ --cov=src`: 492 passed, coverage 92%. `scripts/benchmark_grpc.py`: PASS.

## Debug: Test MAE/RMSE không đạt target (bổ sung 2026-07-25)

Kết quả lần train Kaggle đầu tiên (checkpoint `soh_mamba_v2.0-lfp.pth` hiện có trong
`models/weights/`, chưa commit): **Test MAE 2.5856% (target <2.0%), Test RMSE 3.4745%
(target <3.0%)** — không đạt cả 2 target.

**Root cause #1 (chính, gần như chắc chắn) — undertraining do bug trong notebook:**
`notebooks/kaggle_train_lfp.ipynb` cell 12 gọi `train.py --epochs 5`, trong khi
`scripts/train.py` mặc định `--epochs 100`, `ReduceLROnPlateau(patience=5)`, early-stop
`PATIENCE=15` (`config.py`). Với 5 epoch, LR scheduler **chưa từng trigger** (cần ≥5 epoch
không cải thiện) và early-stop cũng chưa chạm ngưỡng — model gần chắc chắn chưa hội tụ.
Mâu thuẫn với chính ghi chú ở markdown cell 11 ("hyperparameter GIỮ NGUYÊN — chỉ đổi data +
output path"). **Fix:** đổi `--epochs 5` → `--epochs 100` trong notebook (khớp default thật
sự dùng để train model NASA v1.6).

**Root cause #2 (phụ, verify được trong code) — `CYCLE_COUNT_NORM` sai domain cho Severson:**
`scripts/preprocess_lfp.py` copy nguyên `CYCLE_COUNT_NORM=200.0` từ NASA (cell dài nhất quan
sát ~197 cycle), nhưng Severson cell chạy tới **~2300 cycle** (chính comment cũ trong file đã
ghi nhận điều này nhưng chưa fix). Hệ quả: mọi window sau cycle #200 (= đa số dữ liệu Severson)
bị `np.clip(cycle_idx/200, 0, 1)` dồn cứng về `cycle_count_norm=1.0` — cột feature mất khả năng
phân biệt cell ở cycle 250 với cycle 2000 dù SOH khác xa nhau → nhiễu tín hiệu training.
**Fix:** thêm `LFP_CYCLE_COUNT_NORM=2300.0` vào `src/core/config.py`, `preprocess_lfp.py` dùng
hằng số này thay vì `200.0` local.

**⚠️ Follow-up bắt buộc khi làm bước "Chemistry-aware artifact selection" (chưa làm — xem mục
"Chưa làm" ở trên):** `src/services/inference.py::_append_derived_features()` hiện luôn dùng
`CYCLE_COUNT_NORM` (=200, global NASA) từ `config.py` để normalize `cycle_count` lúc inference,
KHÔNG phân biệt chemistry. Khi wiring model LFP vào `model_loader.py`/`inference.py`, nhánh xử
lý request `chemistry=="LFP"` PHẢI dùng `LFP_CYCLE_COUNT_NORM` (2300), không phải
`CYCLE_COUNT_NORM` (200) — nếu không sẽ lệch hẳn so với lúc train, dự đoán sai mà không có lỗi
nào được raise (silent mismatch, giống loại lỗi mà `.claude/rules/tech/ai.md` yêu cầu tránh
bằng version assertion).

**Chưa fix (không đủ evidence để khẳng định là bug, chỉ là giả thuyết cần theo dõi nếu sau khi
train lại vẫn không đạt target):**
- Severson dùng protocol sạc nhanh đa bước (CC-CC-CC-CC-CV, nhiều bước dòng khác nhau) phức tạp
  hơn nhiều so với đường xả đơn giản của NASA — nếu cycle "cycles_grp" trong .mat gộp cả sạc lẫn
  xả vào 1 mảng liên tục, window 30-step có thể rơi vào đoạn chuyển pha sạc→xả, khác hẳn phân bố
  NASA. Cần xem log Kaggle đầy đủ (train loss theo epoch) sau lần train lại để biết model có
  underfit (train loss cũng cao — do thiếu epoch, khớp root cause #1) hay đã hội tụ nhưng vẫn
  miss target (→ do đặc thù dữ liệu, cần xử lý riêng, ví dụ tách sạc/xả trước khi window).
- Test set chỉ ~5% cell (`--test-frac 0.05`, mặc định) — với ~124 cell tổng, test set nhỏ
  (~6 cell) nên MAE/RMSE có thể có variance đáng kể giữa các lần chạy; không phải nguyên nhân
  chính nhưng nên biết khi so sánh số liệu.

**Bằng chứng phụ xác nhận root cause #1 (tìm thấy 2026-07-25):** `scripts/train.py` chỉ in dòng
metric per-epoch ở mức INFO khi `epoch % 10 == 0` (line ~370); chi tiết từng epoch là
`logger.debug` (line ~365, không hiện ở mức log mặc định). Với `--epochs 5`, **KHÔNG có một dòng
epoch nào được in ra** (1..5 đều không chia hết cho 10) — log Kaggle nhảy thẳng từ
"Starting training..." sang kết quả test. Đây là lý do log chỉ ~99 dòng và không thấy được
train/val loss để chẩn đoán. Khi chạy lại với `--epochs 100` sẽ có 10 dòng epoch (10, 20, ..., 100)
để đối chiếu train loss vs val loss (phân biệt underfit với overfit).

**⚠️ RỦI RO THỜI GIAN CHẠY — chưa giải quyết, phát hiện 2026-07-25:** log Kaggle dừng ở
**40142.9s = 11.15 giờ**, sát giới hạn 12h/session của Kaggle. Con số này là của lần chạy CHỈ
5 epoch. Nếu phần lớn 11h đó là training (không phải preprocess), thì `--epochs 100` là **bất
khả thi** trong 1 session — session sẽ bị Kaggle kill giữa đường, mất hết. Nguyên nhân gốc là
quy mô dataset: Severson có ~124 cell × 800–2300 cycle/cell (so với NASA ~170 cycle/cell), mỗi
cycle lại sinh nhiều window ở `WINDOW_STRIDE=30` → tổng số window có thể lớn gấp hàng chục lần
NASA. **Cần đọc log đầy đủ (dòng `Train: N | Val: N | Test: N` + timestamp của "Loading data..."
vs "Starting training...") để biết tỉ lệ preprocess/train trước khi quyết định.** Hướng fix khả
năng cao nhất nếu training là phần chậm: thêm option subsample cycle trong `preprocess_lfp.py`
(vd `--cycle-stride 5` — giữ mỗi cycle thứ 5), vì SOH giữa các cycle liên tiếp của Severson gần
như không đổi → dataset nhỏ đi 5x mà gần như không mất thông tin, đồng thời giảm cả thời gian
preprocess. KHÔNG hạ epoch xuống lại — đó chính là nguyên nhân gây ra vấn đề ban đầu.

**Việc cần làm tiếp:**
- [ ] **BẮT BUỘC TRƯỚC KHI CHẠY LẠI — commit + push 3 file đã sửa lên GitHub** (`src/core/config.py`,
  `scripts/preprocess_lfp.py`, `notebooks/kaggle_train_lfp.ipynb`) **VÀ re-upload/paste lại
  notebook trên Kaggle UI.** Lần chạy 11h vừa rồi ra kết quả y hệt vì cả 2 đường này đều chưa
  được cập nhật: notebook cell 12 trên Kaggle vẫn `--epochs 5`, và `git clone --depth 1` trong
  notebook kéo code từ **remote** nên vẫn nhận `CYCLE_COUNT_NORM=200`. Sửa file trên máy local
  KHÔNG tự động tới Kaggle.
- [ ] Chạy lại `notebooks/kaggle_train_lfp.ipynb` trên Kaggle (đã sửa `--epochs 100` +
  `preprocess_lfp.py` dùng `LFP_CYCLE_COUNT_NORM`) — **phải chạy lại bước preprocess** (cell 10)
  trước train vì cycle_count_norm nằm trong `data/processed_lfp/*.pt`, không chỉ trong config.
- [ ] Tải zip mới, ghi đè 4 file hiện có trong `models/weights/` (`soh_mamba_v2.0-lfp.pth`,
  `isolation_forest_v2.0-lfp.pkl`, `scaler_lfp.pkl`, `feature_scaler_lfp.pkl`) — 4 file đang có
  trong working tree là kết quả của lần train lỗi (MAE 2.59%), CHƯA commit, không dùng được.
- [ ] Nếu vẫn miss target sau khi fix 2 bug trên → xem lại giả thuyết "sạc/xả gộp chung cycle"
  ở trên trước khi thử tune thêm hyperparameter.

### Fix vòng 2 (2026-07-25) — giải quyết rủi ro 12h + đo được thời gian

- [x] `scripts/preprocess_lfp.py`: thêm `--cycle-stride N` (default 1 = giữ nguyên behavior).
  Notebook set `--cycle-stride 5` → dataset/preprocess/train nhỏ đi ~5x. Căn cứ: Severson
  800–2300 cycle/cell, SOH giữa 2 cycle liền nhau chênh ~0.01–0.02% → dùng hết là dư thừa;
  stride 5 vẫn còn 160–460 cycle/cell (ngang mật độ per-cell của NASA ~170) và phủ nguyên
  khoảng SOH.
- [x] **Bug thứ 3 phát hiện khi làm subsample** — `kept_cycles.append((cycle_arr, soh,
  len(kept_cycles)))` dùng "vị trí trong các cycle được giữ" làm `cycle_idx` (copy quy ước NASA,
  `scripts/preprocess.py:114`). Quy ước đó chỉ đúng vì NASA gần như không drop cycle nào; dưới
  subsample nó **nén trục tuổi pin đúng bằng cycle_stride** (cycle 2000 báo thành 400) → lệch
  hẳn so với inference, nơi BE gửi cycle_count thật (`inference.py::_raw_cycle_count`). Đã đổi
  sang dùng `j` = số cycle thật trong file .mat.
- [x] Thêm log `[TIMING]` vào preprocess: tách riêng thời gian `.mat parse` vs
  `window+feature extraction` vs total, kèm số step/epoch ở batch=32. Lần chạy tới sẽ **tự trả
  lời** câu hỏi "preprocess hay train mới là phần ngốn 11h" mà không cần đoán.
- [x] Metadata `scaler_lfp.pkl` thêm `cycle_stride` + `cycle_count_norm` để trace (2 giá trị này
  đổi là model học khác đi, và `cycle_count_norm` bắt buộc phải khớp lúc inference).
- [x] Notebook: cell 10 thêm `--cycle-stride 5`; markdown cell 9/13 ghi rõ cách đọc log
  `[TIMING]` và cách đọc TrainLoss vs ValLoss để phân biệt underfit / overfit / đã hội tụ.
- [x] `pytest tests/ -q`: **539 passed** (không có test nào cho preprocess_lfp.py vì h5py không
  cài local — verify bằng `ast.parse` + chạy `--help` với h5py stub).

## Kết quả train lần 2 (2026-07-25) — ĐẠT TARGET

`models/weights/soh_mamba_v2.0-lfp.pth` (mtime 21:19):

| Metric | Lần 1 (5 epoch) | **Lần 2** | Target | |
|--------|-----------------|-----------|--------|---|
| Test MAE | 2.5856% | **1.9213%** | < 2.0% | ✅ |
| Test RMSE | 3.4745% | **2.7627%** | < 3.0% | ✅ |

Xác nhận root cause #1 (undertraining) là đúng. Smoke-check: checkpoint load `strict=True` vào
`MambaSOHPredictor` không thiếu/thừa tensor; forward pass trên window LFP giả lập cho SOH
94–97% (hợp lý cho cell khỏe), iso_forest `contamination=0.1/n_estimators=100/random_state=42`
đúng spec.

**Lần chạy này KHÔNG dùng round-2 fix** — `scaler_lfp.pkl` metadata thiếu key `cycle_stride`/
`cycle_count_norm` (2 key mà code round 2 ghi vào), và 3 artifact scaler/feature_scaler/
iso_forest byte-identical với lần 1 → preprocess chạy lại bằng code round 1. Cải thiện đến
thuần từ round 1 (`--epochs 100` + `CYCLE_COUNT_NORM` 200→2300).

### ⚠️ Bug thứ 4 (phát hiện 2026-07-25 khi verify artifact) — outlier phi vật lý phá scaler

`MinMaxScaler` fit trên `data_min_/data_max_`, nên chỉ cần 1 mẫu lỗi là hỏng cả kênh. Đo trực
tiếp trên `scaler_lfp.pkl` hiện tại:

| Kênh | Scaler fit trên | Khoảng vận hành thật | Chiếm % của [0,1] | Mất độ phân giải |
|------|-----------------|----------------------|-------------------|------------------|
| temperature | **[-270.0, 400.0]** | 28–45 °C | **2.54%** | **39.4x** |
| voltage | **[0.736, 6.606]** | 2.0–3.65 V | 28.11% | 3.6x |
| current | [-12.213, 8.169] | -4.4–8.8 A | 64.76% | 1.5x |

`-270°C`/`400°C` là sentinel lỗi thermocouple trong bản export Severson — **finite nên lọt qua
`np.isfinite()` check** đang có. Hệ quả: kênh temperature coi như **chết** (biến thiên thật chỉ
chiếm 2.5% dải scaled), voltage mất 3.6x độ phân giải. Đây là ứng viên số 1 giải thích vì sao
model LFP (MAE 1.92%) kém hơn hẳn model NASA v1.6 (MAE 1.34%) dù cùng kiến trúc.

**Đã fix:** thêm `PHYSICAL_RANGES` (voltage [1.0,4.5], current [-25,25], temp [-20,80] — cố tình
lỏng, chỉ bắt sentinel chứ không siết envelope vận hành, vì Severson sạc nhanh tới ~8A/7.4C là
hợp lệ) + `_nonphysical_channel()` drop nguyên cycle chứa mẫu lỗi, kèm log đếm số cycle bị drop
và in dải scaler sau khi fit để lần chạy tới tự xác nhận.

> Nếu log báo drop một tỉ lệ LỚN cycle → chuyển từ drop sang clip mẫu lỗi, vì lúc đó đang vứt đi
> dữ liệu train thật. Số cycle bị drop được in ngay trong log preprocess.

### Notebook viết lại (2026-07-25) — `notebooks/kaggle_train_lfp.ipynb`, 21 cell

- **Cell 3 mới — guard kiểm tra version code clone về.** Assert `--cycle-stride`/
  `PHYSICAL_RANGES`/`_nonphysical_channel` có trong `preprocess_lfp.py`, `--feature-scaler-version`
  /`--mamba-out`/`--iso-out` trong `train.py`, `LFP_CYCLE_COUNT_NORM` trong `config.py`. Fail →
  dừng ngay kèm hướng dẫn `git push` + Restart & Run All. **Chặn đúng cái bẫy đã đốt ~11 giờ**
  (notebook sửa rồi nhưng code chưa push → clone về vẫn bản cũ). Đã test 2 chiều: pass trên code
  local (đủ fix), chặn đúng trên code HEAD hiện tại (thiếu 3 symbol).
- **KHÔNG bật `--cycle-stride`.** Lần train 2 chạy full data vẫn xong trong 12h → lo hết giờ là
  thừa, mà cắt 5× dữ liệu lúc này có nguy cơ làm MAE tệ đi. Giữ nguyên full data để **chỉ đổi 1
  biến** (lọc outlier) → biết chính xác nó đóng góp bao nhiêu. Flag vẫn còn, dùng làm đường lui
  nếu session sắp hết giờ (ghi rõ trong markdown cell 6).
- Cell 8 so metric với baseline lần 2 (1.9213/2.7627) và **in dải scaler sau train** để xác nhận
  `PHYSICAL_RANGES` đã ăn (kỳ vọng temperature ~[25,50] thay vì [-270,400]).
- Cell 1 assert CUDA khả dụng (trước chỉ warn), checklist 4 bước + bảng lịch sử kết quả ở cell 0.

### Bug thứ 5 (2026-07-25) — window lẫn pha SẠC, trong khi NASA/inference chỉ có pha XẢ

**Đây là chênh lệch lớn nhất giữa pipeline LFP và NASA.** `scripts/preprocess.py::load_cycles()`
lọc `meta["type"] == "discharge"` — NASA **chỉ nạp chu kỳ xả**. `preprocess_lfp.py` thì đọc
nguyên `cycles_grp["V"/"I"/"T"/"t"]`, tức **cả sạc nhanh nhiều bước (CC1–CC4–CV, dòng dương tới
~8 A) lẫn xả 4C** trong cùng 1 mảng, rồi cắt window trượt qua toàn bộ.

Hệ quả:
1. ~Nửa số window nằm trong pha **sạc** — phân bố mà model production **không bao giờ gặp**
   (BE gửi telemetry xả).
2. Nhãn SOH lấy từ `QDischarge` (dung lượng **xả**) — bắt model hồi quy nhãn xả từ mẫu sạc.
3. Dòng sạc dương / xả âm trộn chung làm dải scaler current rộng ra và thống kê window bimodal.

**Đã fix:** `_longest_discharge_segment()` — lấy đoạn xả liên tục dài nhất, dùng lại
`compute_phase_mask` từ `src/features/extractor.py` (2 = xả, `current < -0.1A`) để convention
nằm đúng 1 chỗ; rebase `time` về 0 khớp file per-cycle của NASA (`time` vừa là input channel vừa
là trục tích phân của `compute_soc_percent`). CLI `--phase discharge|all`, default `discharge`;
`all` giữ behavior cũ để ablation.

### Bug thứ 6 (2026-07-25) — cột `time` có giá trị âm + nghi sai đơn vị

`scaler_lfp.pkl` cho `time` range **[-57510.7, 4825.5]** — thời gian trôi trong 1 cycle không thể
âm. Đã thêm `"time": (0.0, 200_000.0)` vào `PHYSICAL_RANGES` (trước chỉ check 3 kênh đầu).

**Chưa kết luận được — cần số liệu từ lần chạy tới:** `compute_soc_percent()` giả định `time`
tính bằng **giây** (`t_hours = time / 3600`, đúng convention NASA và đúng cái BE gửi lúc
inference). Nếu Severson lưu bằng **phút** thì kênh `soc_percent` lệch 60×, coi như chết giống
kênh temperature. Đã thêm log in **trung vị thời lượng đoạn xả**: xả 4C kéo dài ~15 phút → trung
vị ~900 nghĩa là giây (khớp NASA), ~15 nghĩa là phút (phải sửa).

### Các knob train CHƯA dùng (đã xác minh trong code)

`train()` cho path window=30 chỉ nhận 4 tham số: `epochs`, `balance_bands`, `jitter`, `swa`
(+`swa_start_frac`). Mọi flag khác của `train.py` (`--pooling`, `--patch-size`,
`--attention-heads`, `--dropout`, `--weight-decay`, `--weighted-loss`, `--cosine-t0`,
`--accum-steps`…) **chỉ đi vào path `--long`**, không ảnh hưởng window=30. Checkpoint LFP lần 2
ghi `balance_bands: False, jitter: 0.0, swa: False` → chưa dùng knob nào.

> ⚠️ `--balance-bands` **yếu với dữ liệu LFP**: `_balance_band_weights()` chia SOH thành
> `n_soh_bins=10` trên thang [0,100], mà Severson chỉ trải ~80–100% → rơi vào đúng **2 bin**;
> đồng thời Severson chỉ có **1 mức nhiệt (30°C)** nên chiều `n_temp_bins=3` của lưới cũng sụp.
> Flag này sinh ra cho NASA (3 mức nhiệt, SOH trải rộng) nên đừng kỳ vọng nhiều ở LFP.

### Thứ tự chạy đề xuất (để quy trách nhiệm được cho từng thay đổi)

1. **Lần 3** — chỉ 2 fix đúng đắn (`--phase discharge` + `PHYSICAL_RANGES`), không bật knob nào.
   Đây là fix *correctness*, không phải tuning, nên gộp chung 1 lần là hợp lý.
2. **Lần 4** (nếu còn muốn ép) — thêm `--swa`, rồi `--jitter 0.01`. Từng cái một.

### Log Kaggle đầy đủ lần 2 (đọc được 2026-07-26) — ĐÍNH CHÍNH 2 kết luận sai trước đó

**Sai #1 — "undertraining do `--epochs 5`" là SAI.** Log lần 2 dòng 78 ghi
`Config: lr=0.0005, batch=32, epochs=5, patience=15` → **lần 2 CŨNG chạy 5 epoch**, và dòng 39
ghi clone được `f0f3996` (code round-1). Nghĩa là toàn bộ cải thiện 2.5856 → 1.9213 đến từ fix
`CYCLE_COUNT_NORM` 200→2300, **không liên quan số epoch**. `--epochs 100` chưa từng chạy.

**Sai #2 — "full data vẫn xong trong 12h nên bỏ `--cycle-stride`" là SAI.** Số đo thật:

| Bước | Thời gian |
|------|-----------|
| Parse 4 file `.mat` (141 cell) | 266s (4,5 phút) |
| Trích xuất window+feature train (3 220 853 window) | 13 293s (**3,7h**) |
| Trích xuất val/test | 1 427s (24 phút) |
| Train **5 epoch** | 25 147s (**7,0h** → **1,4h/epoch**) |
| Tổng | **11,2h** / giới hạn 12h |

→ 100 epoch full data = **140 giờ**, vượt giới hạn **12 lần**. `--cycle-stride` là **bắt buộc**.
Lần 2 chỉ vừa khít 12h vì nó chạy 5 epoch, không phải vì full data rẻ.

### ⚠️ Phát hiện quan trọng nhất — model hỏng ở vùng EOL, MAE tổng che mất

Log lần 2, `Per-band test MAE` (band 10 điểm, từ `train.py` GH-88):

| Dải SOH | n | MAE | bias |
|---------|---|-----|------|
| 70–80% | 950 | **10.293%** | **+10.280%** |
| 80–90% | 19 310 | 4.139% | +3.845% |
| 90–100% | 150 080 | 1.507% | −0.878% |

Pin thật 75% SOH → model dự đoán **~85%**. Đây là failure mode **tệ nhất có thể** cho hệ thống
bảo trì: pin đã qua ngưỡng EOL 80% bị báo là còn khoẻ → **bỏ sót pin cần thay**, đúng thứ sản
phẩm sinh ra để phát hiện. MAE tổng 1.92% "đạt target" chỉ vì dải 90–100% chiếm **88%** số mẫu
test (150 080/170 340).

Nguyên nhân: mất cân bằng **158:1**. Đây chính xác là ca dùng của `--balance-bands`
(comment trong `train.py`: *"the v1.5 failure mode was concentrated in the 75-85% band"*).

**Sai #3 — tôi từng viết `--balance-bands` "yếu với LFP" vì tưởng SOH chỉ trải 80–100% → 2 bin.
Log cho thấy trải 70–100% → 3 bin và lệch 158:1. Kết luận đó SAI, flag này là ưu tiên số 1.**

### Cấu hình lần 3 (notebook đã set sẵn)

`--cycle-stride 5 --phase discharge` + `--epochs 50 --balance-bands`
→ ước tính ~290k window, ~450s/epoch, 50 epoch ≈ 6,3h + preprocess ~27 phút ≈ **7h tổng**.

Cell 8 của notebook giờ **đọc lại per-band từ file log** và so `bias` dải 70–80% với mốc
+10.280% của lần 2 — đây mới là chỉ số quyết định, không phải MAE tổng. Cell cũng
`assert scaler['phase'] == 'discharge'` để không bao giờ nhầm artifact cũ/mới nữa.

> Ghi chú nhỏ, không phải bug: dòng log `Training IsolationForest on spectral features (54 dims)`
> là chuỗi hardcode cũ trong `train.py`; số chiều thật là 57 (`SPECTRAL_FEAT_DIM`). Không ảnh
> hưởng kết quả, để lại vì ngoài scope.

## Kết quả lần 3 (2026-07-27) — ĐẠT TARGET, gần ngang model NASA

| Metric | Lần 2 | **Lần 3** | Target | NASA v1.6 |
|--------|-------|-----------|--------|-----------|
| Test MAE | 1.9213% | **1.4365%** | < 2.0% | 1.3409% |
| Test RMSE | 2.7627% | **1.8767%** | < 3.0% | 1.8426% |

MAE giảm 25%, **RMSE giảm 32%**. RMSE cải thiện mạnh hơn MAE nghĩa là các sai số **lớn** co lại
nhiều hơn sai số điển hình — dấu hiệu tốt cho thấy bias +10.28% ở dải EOL đã giảm đáng kể
(cần số per-band từ log để xác nhận chắc chắn).

Metadata xác nhận đủ 4 fix đã ăn: `cycle_stride: 5`, `cycle_count_norm: 2300.0`,
`phase: discharge`, `balance_bands: True`. Dải scaler đã sạch hoàn toàn:

| Kênh | Lần 2 (hỏng) | Lần 3 |
|------|--------------|-------|
| voltage | [0.736, 6.606] | **[1.889, 3.595]** — đúng dải LFP |
| current | [-12.213, 8.169] | **[-4.265, -0.100]** — toàn ÂM = thuần pha xả ✅ |
| temperature | [-270.0, 400.0] | **[0.000, 44.365]** |
| time | [-57510.7, 4825.5] | **[0.000, 24.130]** |

126/141 cell vào train (1 cell không có đoạn xả đủ 30 bước).

### 🚨 Bug thứ 7 — cột `time` của Severson là PHÚT, không phải giây (CHẶN PRODUCTION)

Dải `time` sau fix = **[0.000, 24.130]**. Xả 4C của cell 1.1 Ah kéo dài ~15 phút → 24.13 là
**phút**. (24 *giây* cho một lần xả 4C là bất khả thi về vật lý.) NASA và payload BE gửi đều
dùng **giây**.

Đo trực tiếp, 2 hậu quả:

1. **Kênh `soc_percent` chết trong lúc train.** `compute_soc_percent()` làm
   `t_hours = time / 3600` tức giả định giây. Cho ăn phút → đếm thiếu điện lượng 60×:
   window 12 phút xả 4A cho `soc 100.00 → 98.79` (đúng phải là `100.00 → 27.27`). Gần như
   phẳng, model mất hẳn 1 trong 6 kênh input.
2. **Nghiêm trọng hơn — lệch phân bố lúc inference.** BE gửi giây, nhưng scaler fit trên phút:

   | `time` BE gửi | Sau scaler | |
   |---|---|---|
   | 0 s | 0.00 | |
   | 60 s | **2.49** | ngoài phân bố |
   | 300 s | **12.43** | ngoài phân bố |
   | 720 s | **29.84** | ngoài phân bố |

   Train chỉ từng thấy [0, 1]. Không có lỗi nào được raise — model cứ thế predict sai.

**Đã fix:** `TIME_UNIT_SECONDS` + `--time-unit {minutes,seconds}` (default `minutes`) quy `time`
về **giây** ngay lúc parse, trước mọi thứ khác. Metadata scaler thêm `time_unit_in` để trace.
Sau fix, `time` sẽ nằm dải ~[0, 1448] giây thay vì [0, 24.13].

> Fix này **bắt buộc** trước khi wire model LFP vào inference, và nhiều khả năng còn cải thiện
> thêm metric vì hồi sinh kênh `soc_percent` đang chết.

## Mục tiêu mới (2026-07-27): cả MAE và RMSE < 1.0%

**Đánh giá trung thực: MAE < 1% khả thi, RMSE < 1% khó.** RMSE ≥ MAE luôn; tỉ lệ hiện tại
`1.8767/1.4365 = 1.31` → muốn RMSE < 1.0 thì MAE phải xuống **~0.77%**, tức cải thiện **47%**.
Chưa model nào của dự án xuống dưới 1% (NASA v1.6: 1.34/1.84; long-seq v2.2: 1.52/1.97).

### Vì sao fix #7 là đòn bẩy mạnh nhất (không chỉ là fix production)

Mọi window cắt từ **cùng 1 chu kỳ xả** mang **chung 1 nhãn SOH**. Window 30 bước chỉ là lát cắt
nhỏ trong ~15 phút xả: lát đầu (3.4 V) và lát cuối (2.9 V) trông khác hẳn nhau nhưng phải cho ra
cùng một con số. Model chỉ phân giải được nếu biết **đang ở đoạn nào của quá trình xả** — tín
hiệu đó chính là `soc_percent`/`time`, mà `soc_percent` đang **chết** vì bug #7. Đây là phương
sai nội-chu-kỳ không thể khử nếu thiếu thông tin vị trí → fix #7 tấn công trực diện nguồn sai số
lớn nhất còn lại.

### Cấu hình lần 4 (user chốt 2026-07-27)

`--cycle-stride 5 --phase discharge --time-unit minutes` + `--epochs 50 --balance-bands --swa`
→ giữ stride 5 để **cô lập** đóng góp của fix #7 + SWA, ~7h.

`--swa` rủi ro rất thấp: `train.py` chỉ dùng trọng số SWA **nếu val_loss tốt hơn** best
checkpoint, không thì `model.load_state_dict(best_state)` revert. Với `epochs=50`,
`swa_start_frac=0.75` → SWA gộp từ epoch 38, `effective_patience = max(15, 50-38+5) = 17`.

### Đòn bẩy còn lại (chưa dùng), xếp theo giá trị

| # | Đòn bẩy | Kỳ vọng | Ghi chú |
|---|---------|---------|---------|
| 1 | Fix #7 (hồi sinh `soc_percent`) | Cao | lần 4 |
| 2 | `--swa` | 5–15% tương đối | lần 4 |
| 3 | `--cycle-stride 2` (gấp 2.5× dữ liệu) | Vừa | phải giảm còn ~25 epoch để vừa 12h |
| 4 | `--jitter 0.01` | Thấp–vừa | chỉ khi log cho thấy overfit |
| 5 | `d_model` 64→128 (79 467 params là rất nhỏ) | Có thể cao | ⚠️ **lệch spec `CLAUDE.md`** — cần quyết định riêng; `train.py` chưa có flag `--d-model` |

> Về #5: `model_loader.py:74-75` đọc `d_model`/`d_state` **từ checkpoint**
> (`checkpoint.get("d_model", 64)`), nên model to hơn vẫn load được mà không phải sửa code
> inference. Rào cản duy nhất là spec, không phải kỹ thuật.

### Còn thiếu để tư vấn chắc chắn

**3 dòng `Per-band test MAE` của lần 3.** Sai số còn lại nằm ở dải SOH nào quyết định đòn bẩy nào
đáng dùng — tập trung ở dải 70–80% thì hướng khác hẳn với khi rải đều. Chưa có số đó thì phần
xếp hạng trên có phần suy đoán.

### 🚨 Bug thứ 8 (2026-07-27) — 7 đặc trưng khuếch đại nhiễu làm tròn 15.000–93.000×

Đo trực tiếp `feature_scaler_lfp.pkl` lần 3: **12/57 đặc trưng có `var < 1e-8`** (NASA chỉ 4),
trong đó **7 cái có `var` ở mức 1e-10…4e-9** — tức chỉ là nhiễu làm tròn float. `StandardScaler`
chia cho `sqrt(var)` nên biến nhiễu đó thành tín hiệu biên độ đơn vị:

| idx | Đặc trưng | var | Khuếch đại |
|-----|-----------|-----|------------|
| 20 | `spec.temp.centroid` | 1.15e-10 | **93.072×** |
| 27 | `spec.temp.band_mid` | 1.70e-10 | 76.739× |
| 28 | `spec.temp.band_high` | 2.54e-10 | 62.733× |
| 26 | `spec.temp.band_low` | 8.26e-10 | 34.788× |
| 29 | `spec.temp.gini` | 1.40e-09 | 26.727× |
| 53 | `stat.temp.waveform` | 2.60e-09 | 19.610× |
| 24 | `spec.temp.flatness` | 4.32e-09 | 15.210× |

Gần trọn khối **phổ nhiệt độ** (layout feature: `[spec×3ch(10), stat×3ch(9)]`, idx 20–29 =
spectral temperature). Severson chạy buồng 30 °C → nhiệt độ gần như hằng số trong window 30 bước
→ FFT là DC thuần → mọi mô tả hình dạng phổ suy biến.

**Vì sao hại nặng:** 7 kênh này vào `film_proj` (`Linear(57→57)→SiLU→Linear(57→128)`), sinh
`gamma`/`beta` **điều biến MỌI hidden unit** của model. Nhiễu lan ra toàn bộ biểu diễn → biểu
hiện thành phương sai dự đoán, tức đúng **RMSE** — chỉ số đang là ràng buộc khó nhất.

**Đã fix:** `FEATURE_VAR_FLOOR = 1e-8`, ép `scale_ = 1.0` cho feature dưới ngưỡng ngay sau khi
`fit()` và **trước** khi transform bất cứ split nào → train/val/test/inference đi qua cùng một
ánh xạ. Ngưỡng nằm trong khoảng trống rõ: khối gây hại ở `var ~1e-10`, feature nhỏ nhất có tín
hiệu thật (`spec.voltage.centroid`) ở `~1.4e-6` — cách nhau 4 bậc.

**Không phải sửa code inference:** `inference.py` gọi `model_loader.feature_scaler.transform()`
trên chính file pickle này, nên `scale_` đã vá tự động áp dụng ở cả 2 phía.

Verify bằng dữ liệu mô phỏng (4 cột: signal mạnh / signal nhỏ thật / nhiễu làm tròn / hằng số):
cột nhiễu biên độ `1.000 → 1.1e-05`, 2 cột có tín hiệu thật **không đổi**. Metadata
`feature_scaler_lfp.pkl` thêm `var_floor` + `n_degenerate` để trace; notebook assert
`amp_max < 5000` để bắt trường hợp fix chưa ăn.

## Kết quả lần 4 (2026-07-27) — thắng lớn ở vùng EOL

| Dải SOH | Lần 2 | **Lần 4** |
|---------|-------|-----------|
| 70–80% | MAE 10.293%, bias **+10.280%** | MAE 2.814%, bias **+2.474%** (n=46) |
| 80–90% | MAE 4.139%, bias +3.845% | MAE 1.233%, bias **+0.198%** (n=1856) |
| 90–100% | MAE 1.507%, bias −0.878% | MAE 1.229%, bias −0.186% (n=14257) |

Bias vùng EOL giảm **7,8 điểm**; 3 dải giờ gần như **đồng đều** (1.233 vs 1.229) — model không
còn thiên lệch hệ thống ở vùng pin sắp hỏng. Đây là thứ quyết định cho bài toán bảo trì, quan
trọng hơn MAE tổng.

| Metric | Lần 3 | **Lần 4** |
|--------|-------|-----------|
| MAE | 1.4365% | **1.3095%** ↓ |
| RMSE | 1.8767% | 1.9228% ↑ |

Fix #7 + #8 đều xác nhận ăn: `time [0, 1447.789]` (giây), `n_degenerate=12`, khuếch đại nhiễu
`93.072× → 5.879×`. `swa: False` — SWA bị revert vì val_loss tệ hơn best checkpoint (cơ chế an
toàn hoạt động đúng, chỉ là SWA không giúp lần này).

### Lỗi của tôi trong notebook lần 4 (đã sửa)

1. **Ngưỡng assert quá chặt.** `assert amp_max < 5000` fail ở 5.879×. Thủ phạm:
   `spec.temp.entropy` với `var = 2.89e-8`, nằm **ngay trên** sàn `1e-8` nên lọt lưới.
   → Nâng `FEATURE_VAR_FLOOR` lên **`1e-7`**: bắt 13 feature (var ≤ 2.89e-8), giữ nguyên 5
   feature có tín hiệu thật (var ≥ 3.84e-7) — khoảng cách **13,3×**, vẫn tách sạch.
2. **Lỗi thiết kế nghiêm trọng hơn: assert chẩn đoán abort cả notebook SAU khi train xong
   4 tiếng**, nên cell đóng gói zip không chạy. → Đảo thứ tự: **đóng gói (§8) chạy TRƯỚC chẩn
   đoán (§9)**, và mọi kiểm tra hậu-train chuyển thành cảnh báo `[!]` qua hàm `chk()`, **không
   còn `assert`** nào. Hard-stop chỉ còn ở cell 3 (guard) — tức trước khi tốn giờ GPU.
   > Artifact lần 4 vẫn cứu được: cell dọn dẹp cũng không chạy nên 4 file còn nguyên ở
   > `/kaggle/working/ai-module/models/weights/` trong tab Output, chỉ chưa gom vào zip.

### Vì sao RMSE tăng nhẹ dù MAE giảm — và fix để nhìn thấy

Cộng 3 dải: 46+1856+14257 = 16.159 mẫu, MAE có trọng số = **1.234%**. Nhưng MAE tổng báo
**1.3095%**. Chênh lệch nghĩa là **có mẫu nằm ngoài 3 dải** và chúng sai nhiều hơn.

Nguyên nhân: `train.py` in band bằng `for lo in range(50, 100, 10)` → **mọi mẫu SOH ≥ 100% đều
vô hình**, trong khi `preprocess_lfp.py` giữ nhãn tới 105% (chu kỳ đầu có dung lượng đo vượt
nominal). Đây nhiều khả năng là nơi RMSE bị đội lên.

**Đã sửa:** đổi thành `range(50, 110, 10)` → thêm dải 100–110. Band rỗng tự bị bỏ qua bởi
`if mask.any()` nên **no-op với NASA**. Lần chạy tới sẽ thấy được vùng này.

## Kết quả lần 5 (2026-07-28) — tốt nhất từ trước tới nay, KHÔNG fail

> Lần chạy này **thành công**: 5/5 check `[OK]`, `lfp_artifacts.zip` đã tạo, không traceback.
> Hai dòng `SyntaxWarning` cuối log là của `mistune`/`nbconvert` — thư viện **của chính Kaggle**
> khi render notebook ra HTML, xuất hiện ở mọi lần chạy kể cả các lần thành công trước.

| Metric | Lần 4 | **Lần 5** |
|--------|-------|-----------|
| MAE | 1.3095% | **1.2899%** |
| RMSE | 1.9228% | **1.8935%** |

Xác nhận đủ: `time` max 1447.8 (giây), `discharge duration trung vi ≈ 1000` (khớp NASA),
`n_degenerate=13`, khuếch đại nhiễu **93.072× → 1.615×**, 230.644 window train, 3,9h tổng.

### Dải SOH ≥ 100% lộ ra — đúng giả thuyết

```
SOH  70-80 : n=   46  MAE=2.808%  bias=+2.560%
SOH  80-90 : n= 1856  MAE=1.230%  bias=+0.218%
SOH  90-100: n=14257  MAE=1.209%  bias=-0.135%
SOH 100-110: n=  532  MAE=3.533%  bias=-3.506%   <- trước đây VÔ HÌNH
```

Kiểm chứng số học: `(46×2.808 + 1856×1.230 + 14257×1.209 + 532×3.533)/16691 = 1.2898` — khớp
**chính xác** MAE tổng 1.2899%, tức mọi mẫu test đã được giải trình.

Dải này chiếm **3,2% số mẫu** nhưng gánh **8,7% tổng sai số tuyệt đối** (quá tay 2,7×); với RMSE
(bình phương) còn nặng hơn. Đây là chu kỳ đầu đời có dung lượng đo vượt nominal 1.1 Ah.

**Đã fix — `SOH_CLIP_DEFAULT = 100.0` + `--soh-clip`:** SOH nghĩa là "sức khoẻ so với pin mới",
>100% không phải trạng thái sức khoẻ mà là hệ quả của việc chia cho nominal datasheet. Không gì
phía sau phân biệt 100% với 103% (ngưỡng `health_stage` là 80/85/90 → cả hai đều "Healthy").
Clip thay vì drop để giữ window làm tín hiệu train vùng "rất khoẻ". `MAX_SOH_KEEP = 105` giữ
nguyên làm bộ lọc lỗi đo.

> ⚠️ **Phải trung thực khi báo cáo:** clip cũng đổi nhãn **tập test**, nên một phần cải thiện là
> do định nghĩa chứ không phải model giỏi lên. Nêu rõ khi so với lần 5 (1.2899%/1.8935%).
> Ghi chú này đã viết thẳng vào comment `SOH_CLIP_DEFAULT` trong code.

### Phát hiện: model đang OVERFIT

```
epoch 30: train 0.000348 | val 0.000505   <- val TỐT NHẤT
epoch 40: train 0.000326 | val 0.000589   <- train giảm, val TĂNG
epoch 50: train 0.000310 | val 0.000549
```

Train loss giảm đều, val loss chạm đáy epoch 30 rồi đi lên → overfit rõ. Giải thích luôn vì sao
**SWA bị revert 2 lần liên tiếp** (lần 5: SWA val 0.000496 vs best-ckpt 0.000473) — trung bình
hoá các epoch cuối vốn đã overfit thì vô ích.

### Cấu hình lần 6

`--cycle-stride 3 --phase discharge --time-unit minutes --soh-clip 100`
+ `--epochs 50 --balance-bands --swa --jitter 0.01`

- **`--jitter 0.01`** — chống overfit trực tiếp (nhiễu Gauss lên input). Val vẫn tách khỏi train
  → tăng `0.02`; **cả hai** cùng tệ hơn lần 5 → hạ `0.005` (nhiễu quá mạnh gây underfit).
- **`--cycle-stride 3`** (thay 5) — thêm 66% dữ liệu, cách chống overfit hiệu quả nhất. Lần 5 chỉ
  dùng 3,9/12 giờ nên thừa ngân sách; stride 3 ước tính ~6,4h.
- `--soh-clip 100` — xử lý dải 100–110 ở trên.

## Lần 6 (2026-07-30) — LÙI, và nguyên nhân đã xác định

| Metric | Lần 5 (tốt nhất) | **Lần 6** | Target |
|--------|------------------|-----------|--------|
| MAE | 1.2899% | **2.8390%** | < 2.0% ❌ |
| RMSE | 1.8935% | **3.5785%** | < 3.0% ❌ |

Cấu hình xác nhận áp đúng (`cycle_stride=3, soh_clip=100.0, jitter=0.01, phase=discharge`), nên
không phải chạy sai cờ.

### 🚨 Bug thứ 9 — đoạn xả dài bất thường làm nổ dải `time`

```
Lần 5:  time [0.000,  1,447.789]   <- ~24 phút, hợp lý cho xả 4C
Lần 6:  time [0.000, 25,551.094]   <- 7,1 GIỜ
```

Dải rộng ra **17,6×**. `--cycle-stride 5 → 3` lấy tập cycle khác nhau (0,5,10,… vs 0,3,6,…) và
stride 3 vô tình lấy được một cycle có đoạn "xả" dài 7,1 giờ — protocol Severson xả 4C ~15 phút
nên đây là bất thường (chu kỳ chẩn đoán dòng thấp, hoặc pha bị nhận diện sai).

Hệ quả: window xả bình thường ~900 s từ chỗ chiếm **62%** dải `[0,1]` tụt còn **3,5%** → kênh
`time` mất 17,6× độ phân giải. Mà `time` chính là tín hiệu **vị-trí-trong-chu-kỳ-xả** (mọi window
của 1 chu kỳ mang chung 1 nhãn SOH nên model chỉ phân biệt lát đầu/cuối qua `time`/`soc_percent`)
→ sai số tăng gấp đôi là hợp lý.

**Cùng loại lỗi với #6 (temperature `[-270, 400]`) và #8 (nhiễu feature): một mẫu vô lý làm hỏng
một dải và bóp chết tín hiệu thật.** `PHYSICAL_RANGES["time"] = (0, 200_000)` quá lỏng — chỉ bắt
sentinel, không bắt "đoạn xả dài vô lý".

**Đã fix:**
- `MAX_DISCHARGE_SECONDS = 7200` (2 h — gấp 8× xả 4C nominal ~900 s): loại đoạn xả dài hơn thế.
  Verify bằng mô phỏng: xả 4C (897 s) và xả chậm 1 h (3588 s) **được giữ**; 2,5 h (8970 s) và
  7,1 h (25564 s) **bị loại**.
- In `p50/p95/p99/max` thời lượng đoạn xả thay vì chỉ trung vị — vì vấn đề nằm ở đuôi phân bố.
- In dải scaler cho **cả 4 kênh** (trước chỉ 3) + **cảnh báo lớn** nếu `time` max vẫn vượt ngưỡng,
  kèm tính luôn phần trăm dải mà một window bình thường còn chiếm được.

### ⚠️ Chưa cô lập được: `--jitter 0.01` có góp phần hay không

Lần 6 đổi 3 thứ cùng lúc (stride 3, soh-clip, jitter) nên chưa thể tách. Dải `time` nổ 17,6× gần
như chắc chắn là nguyên nhân **chi phối**, nhưng cần log lần 7 (train/val loss theo epoch) để
biết `--jitter 0.01` có quá mạnh không:
- val vẫn tách khỏi train → giữ hoặc tăng `0.02`
- **cả hai** cùng cao hơn lần 5 → hạ `0.005` (nhiễu quá mạnh gây underfit)

### Model tốt nhất vẫn an toàn

Artifact lần 5 (1.2899%/1.8935%) **đã commit trong git**. Bản trên đĩa hiện là lần 6 (tệ hơn,
chưa commit). Lấy lại lần 5: `git checkout -- models/weights/`.
**KHÔNG commit artifact lần 6.**

## 🚨 Bug thứ 10 (2026-07-30) — `soc_percent` vô dụng khi train, lệch hẳn lúc inference

**Phát hiện cấu trúc lớn nhất từ đầu GH-67 — khác hẳn #6/#8/#9 (đều là outlier làm hỏng dải).**

`compute_soc_percent()` được thiết kế **window-local**; docstring của nó ghi rõ *"SOC is defined
RELATIVE TO THE WINDOW: 100% at the first row"*. `preprocess_lfp.py` gọi nó trên từng lát 30 dòng:

| | Dải `soc_norm` | Biến thiên |
|---|---|---|
| **Train** (window-local) | `[0.912, 1.000]` — mọi window đều 100.0 → 91.2% | **8,8 điểm** |
| **Inference** (BE 6 cột) | `[0.094, 1.000]` — SOC thật của pin | **90,6 điểm** |

Ba hậu quả:

1. **Một trong 6 kênh input bị bỏ không.** `soc_percent` gần như hằng số ở mọi window → model
   thực chất chỉ có **5 kênh hữu ích**.
2. **Mất đúng tín hiệu quan trọng nhất.** Mọi window cắt từ 1 chu kỳ mang **chung 1 nhãn SOH**,
   nên model chỉ phân giải được lát đầu (3.4 V) vs lát cuối (2.9 V) qua tín hiệu **vị trí**. Đây
   chính là lập luận tôi đã dùng để giải thích fix #7 và #9 — nhưng `soc_percent`, kênh *được
   thiết kế* để mang tín hiệu đó, lại đang không mang gì.
3. **Lệch phân bố train/inference.** Model chưa bao giờ thấy `soc_norm < 0.912` khi train, nhưng
   BE gửi xuống tận `0.094`. Payload 6 cột là **default BE dùng thật**
   ([[be-predict-payload-6column-default]]).

**Đã fix — `--soc-mode {cycle,window}`, default `cycle`:** Coulomb-count trên **toàn đoạn xả** rồi
lát ra theo window (tính 1 lần/chu kỳ, không tính lại mỗi lát). Verify trên đoạn xả 4C mô phỏng:
`cycle` biến thiên **90,6 điểm** (window đầu 1.000→0.912, window cuối 0.182→0.094) và khớp đúng
dải BE gửi; `window` giữ 8,8 điểm. Mode `window` giữ lại để ablation.

> ⚠️ **Lưu ý phạm vi:** `scripts/preprocess.py` (NASA) có **cùng vấn đề** — nó cũng gọi
> `compute_soc_percent` window-local. Nghĩa là model NASA v1.6 đang production cũng bị lệch kênh
> này với payload 6 cột. **Chưa sửa** vì ngoài scope GH-67 và v1.6 đã ship; cần issue riêng.

## Đánh giá trung thực về mục tiêu < 1% cả hai chỉ số

Sau khi phân tích lại toàn bộ, **MAE < 1% là khả thi; RMSE < 1% gần như không**, và lý do mang
tính bản chất chứ không phải thiếu tuning:

**1. Số nhãn độc lập bị chặn cứng, không phải số mẫu.** 230.644 window nghe nhiều, nhưng ~10
window/chu kỳ **chung 1 nhãn**, và 2 chu kỳ liền nhau chênh ~0,02% SOH. Số nhãn thực sự phân biệt
được ≈ 126 cell × (100%→80%). Hạ `--cycle-stride` chỉ thêm bản gần-trùng, **không thêm đa dạng
nhãn**. Đây là lý do model 79.467 tham số vẫn overfit được — nghịch lý chỉ giải thích được khi
nhìn vào số nhãn, không phải số mẫu.

**2. LFP có plateau điện áp cực phẳng.** Cả dự án đã ghi nhận điều này (profile ngưỡng riêng cho
LFP ở Mức 1). Trên plateau 3,2–3,3 V, điện áp gần như không đổi theo SOC — nên biến thiên do SOH
lại càng nhỏ. Một window 90 giây nằm giữa plateau mang **rất ít thông tin SOH**. Đây là giới hạn
tín hiệu/nhiễu của window=30 trên LFP, không sửa được bằng hyperparameter.

**3. Sàn nhiễu nhãn.** Nhãn = `QDischarge / 1.1`. Sai số phép đo dung lượng của Severson cộng với
biến thiên cell-to-cell ở cùng mức SOH tạo ra sai số không thể khử, ước lượng ~0,5–1% MAE.
MAE hiện tại 1,29% đã không còn cách sàn đó bao xa.

**Ước lượng có căn cứ cho lần 7** (tính từ per-band lần 5):
- `--soh-clip 100` xoá gần hết sai số dải 100–110 (532 mẫu, MAE 3,533% → ~0,5%):
  `(46×2.808 + 1856×1.230 + 14257×1.209 + 532×0.5)/16691 = 1.193%`
- Cộng fix #10 (hồi sinh kênh vị trí) + #9 + `--jitter`: **MAE ~1,05–1,15%, RMSE ~1,5–1,7%**

RMSE < 1% sẽ cần khử luôn 2 dải đuôi (70–80% đang MAE 2,808%, và dải 100–110 nếu không clip) —
mà dải 70–80% chỉ có **46 mẫu test**, tức bản thân con số đó đã rất nhiễu, không phải thứ tối ưu
được một cách đáng tin.

### Đòn bẩy cấu trúc còn lại (chưa làm, cần quyết định)

| Đòn bẩy | Kỳ vọng | Rào cản |
|---------|---------|---------|
| Đặc trưng dQ/dV (IC curve) cho path window=30 | Cao — IC là phương pháp chuẩn cho LFP trong y văn (`compute_ic_feature` đã có sẵn, đang chỉ dùng cho model long) | Đổi contract 57-dim; cần feature path riêng theo chemistry trong `inference.py` |
| Thay ~38/57 đặc trưng vô dụng | Vừa–cao: `current` hằng số trong xả CC → 19 đặc trưng current gần vô nghĩa; `temperature` buồng ổn định → 13 đã bị ép sàn | Cùng rào cản trên; `feat_dim` đọc từ checkpoint nên kỹ thuật khả thi |
| Chọn val/test có chủ đích (phủ vùng EOL) | Vừa — dải 70–80% chỉ 46 mẫu test là quá mỏng để tin | Đổi cách báo cáo số liệu; `--val-ids/--test-ids` đã có sẵn |
| `d_model` 64→128 | **Thấp** — model đang overfit, thêm dung lượng nhiều khả năng làm tệ hơn | Lệch spec `CLAUDE.md` |

## Lần 7 (2026-07-30) — mọi fix đã ăn, nhưng `--jitter` làm tệ đi

| Metric | Lần 5 | **Lần 7** |
|--------|-------|-----------|
| MAE | **1.2899%** | 1.4220% |
| RMSE | 1.8935% | **1.8883%** |

Metadata xác nhận **toàn bộ** fix đã áp: `cycle_stride=3`, `phase=discharge`,
`time_unit_in=minutes`, `soh_clip=100.0`, `soc_mode=cycle`, `time [0, 1453.9]` (fix #9 ăn —
không còn 25551), `var_floor=1e-07`, `n_degenerate=13`, `amp_max=1618x`, `jitter=0.01`.

**Dự đoán của tôi (MAE ~1,05–1,15%) SAI.** Thực tế 1,4220% — kém cả lần 5 dù tiền xử lý tốt hơn
hẳn. Khác biệt duy nhất đáng nghi: lần 5 `jitter=0.0`, lần 7 `jitter=0.01`.

### Vì sao `--jitter 0.01` phản tác dụng — đo được

Biến thiên **trong 1 window** (sau scale) so với nhiễu σ=0.01:

| Kênh | Biến thiên/window | Nhiễu/tín hiệu |
|------|-------------------|----------------|
| current (xả CC) | 0.0002 | **4608%** |
| temperature | 0.0045 | **223%** |
| voltage (plateau) | 0.0292 | 34% |
| time (window 90 s) | 0.0619 | 16% |
| soc (mode cycle) | 0.088 | 11% |
| voltage (knee) | 0.2339 | 4% |

`train.py` cộng nhiễu **đều tay lên mọi kênh** (`X_batch + jitter * randn_like(X_batch)`), nên nó
đánh mạnh nhất vào đúng các kênh biến thiên **nhỏ trong window** — mà đó chính là
`time`/`soc`/`temperature`, tức tín hiệu **vị trí** vừa được dựng lên ở #7/#9/#10.
**`--jitter` đang xoá đi thứ mà 3 fix trước vừa sửa.**

→ **Lần 8: bỏ `--jitter`**, giữ nguyên mọi thứ khác. Đổi đúng 1 biến. Nếu sau này vẫn cần chống
overfit thì dùng `0.002` (nhiễu/tín hiệu của `time` còn ~3%), tuyệt đối không `0.01`.

### RMSE kẹt ~1,88 qua 3 lần chạy — dấu hiệu đã tới sàn

| | MAE | RMSE |
|---|-----|------|
| Lần 3 | 1.4365% | 1.8767% |
| Lần 5 | 1.2899% | 1.8935% |
| Lần 7 | 1.4220% | 1.8883% |

MAE dao động 1,29–1,44% nhưng **RMSE gần như không đổi (1.877–1.894)** qua cả 3 lần, dù tiền xử
lý thay đổi rất nhiều. Điều này nói lên RMSE đang bị chi phối bởi phần **không** chịu tác động của
các fix đó — gần như chắc chắn là đuôi phân bố (dải 70–80% và biến thiên cell-to-cell ở cùng SOH).

Củng cố kết luận đã nêu: **RMSE < 1% không đạt được bằng con đường hiện tại** (window=30 trên
plateau LFP). Muốn phá sàn này cần đổi *thông tin đầu vào*, không phải hyperparameter — tức đòn
bẩy dQ/dV hoặc window dài hơn.

### Việc còn lại
- [ ] Push round 2 + round 3 (cycle-stride, cycle_idx=j, TIMING, PHYSICAL_RANGES) rồi chạy lại
  Kaggle → kỳ vọng MAE cải thiện thêm nhờ kênh temperature/voltage hồi phục độ phân giải.
- [ ] Chemistry-aware artifact selection (vẫn chưa làm) — nhớ `LFP_CYCLE_COUNT_NORM` (2300),
  xem cảnh báo ở mục trên.
- [ ] Model LFP hiện CHƯA được wire vào inference — `chemistry=="LFP"` vẫn dùng artifact NASA.

## Plan — Chemistry-aware artifact selection (mục "chưa làm" cuối cùng của GH-67)

- Status: PLANNING → IMPLEMENTING | Ngày: 2026-07-31
- Điều kiện cần: đã có checkpoint LFP thật (run 8: MAE 1.3495% / RMSE 1.7904%, đã commit)

### Mục tiêu

Model LFP đã train xong và commit, nhưng `chemistry == "LFP"` ở request **vẫn dùng artifact
NASA**. Bước này wire bộ artifact LFP vào `run_inference()` để request khai báo LFP thực sự
được chấm bằng model LFP.

### Hiện trạng (đã verify trong code)

- `model_loader.py` giữ 4 global module-level: `scaler`, `feature_scaler`, `soh_model`,
  `iso_model` — nạp trong `load_models()` lúc startup, có assert version (fail-fast).
- `load_long_model()` là tiền lệ sẵn có cho việc nạp **bộ artifact thứ 2** (lazy, global riêng,
  assert version riêng). Sẽ theo đúng pattern này.
- `run_inference()` đọc thẳng `model_loader.<global>` ở 8 chỗ; 2 helper module-level
  (`_expected_feature_count`, `_append_derived_features`) cũng đọc thẳng.
- `chemistry` đã chạy tới `run_inference()` từ GH-67 Mức 1 — chỉ mới dùng để chọn ngưỡng cảnh
  báo voltage, chưa dùng để chọn artifact.
- Test patch `model_loader` globals rất nhiều (`test_inference.py` 24 chỗ) → **giữ nguyên tên và
  ý nghĩa 4 global hiện tại** (= bộ NASA) để không phá test; bộ LFP đi vào global mới.

### Quyết định thiết kế (nêu rõ để bạn bác nếu không đồng ý)

1. **Nạp bộ LFP lúc startup, best-effort.** `load_long_model()` là lazy, nhưng long-model không
   nằm trên hot path production. LFP thì có (BE gửi `chemistry="LFP"` thật), nên lazy sẽ khiến
   **request đầu tiên** gánh toàn bộ chi phí nạp + `torch.compile` → nguy cơ vỡ SLA <100ms đúng
   ở request đầu. Nạp lúc startup; **thiếu artifact thì KHÔNG crash server** (chỉ log warning),
   vì deploy chỉ chạy NASA vẫn phải bật được.
2. **Request `chemistry="LFP"` mà không có artifact LFP → raise lỗi rõ ràng**, KHÔNG âm thầm rơi
   về weight NASA. Chấm dữ liệu LFP bằng model NASA đúng là kiểu "silent wrong prediction" mà
   `.claude/rules/tech/ai.md` yêu cầu tránh.
3. **`cycle_count_norm` phải theo chemistry**: LFP dùng `LFP_CYCLE_COUNT_NORM=2300`, NASA dùng
   `CYCLE_COUNT_NORM=200`. Đây là cảnh báo đã ghi từ trước — sai chỗ này lệch train/inference mà
   không raise lỗi nào.
4. **Không đổi ngưỡng anomaly theo chemistry** ở bước này. `classify_anomaly()` dùng ngưỡng
   score cố định (-0.1/-0.3) vốn hiệu chỉnh cho iso-forest NASA; iso-forest LFP có phân phối
   score riêng. Đây là việc riêng, cần dữ liệu để hiệu chỉnh — ghi vào "còn lại", không đoán bừa.

### Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/model_loader.py` | modify | Thêm global `lfp_scaler/lfp_feature_scaler/lfp_soh_model/lfp_iso_model` + `load_lfp_models()` (assert version `LFP_MODEL_VERSION`, warm-up `torch.compile` cả eval+train mode như bộ NASA). `load_models()` gọi best-effort ở cuối. |
| `src/services/inference.py` | modify | `_resolve_artifacts(chemistry)` trả bundle (scaler, feature_scaler, soh_model, iso_model, cycle_count_norm, artifact_set). `run_inference()` dùng bundle thay vì đọc global. 2 helper nhận thêm tham số. Metadata thêm `artifact_set` + `model_version`. |
| `src/routers/health.py` | modify | Báo `lfp_loaded` để biết bộ LFP có sẵn sàng không |
| `tests/test_model_loader.py` | modify | `load_lfp_models()` assert version sai → raise; thiếu file → raise |
| `tests/test_inference.py` | modify | `chemistry="LFP"` dùng bundle LFP + `cycle_count_norm=2300`; `chemistry=None` giữ nguyên NASA; LFP thiếu artifact → raise |

### Ngoài scope bước này

- Hiệu chỉnh ngưỡng anomaly cho iso-forest LFP (cần dữ liệu, không đoán)
- Sửa `scripts/preprocess.py` (NASA) cho bug #10 — model v1.6 đã ship, cần issue riêng
- Đặc trưng dQ/dV
- gRPC: `chemistry` đã có sẵn trong `PackConfig` từ Mức 1 nên không phải đụng proto

### Lưu ý bắt buộc ghi vào docs

Model LFP được train với `soc_mode=cycle` (soc tính trên toàn đoạn xả). Payload **4 cột** khiến
inference tính soc window-local → lệch hẳn phân bố. **LFP nên luôn dùng payload 6 cột** (BE gửi
SOC thật) — đúng default BE đang dùng.

### Steps

- [x] 1. `model_loader.py`: `load_lfp_models()` + globals + gọi best-effort trong `load_models()`
- [x] 2. `inference.py`: `_resolve_artifacts()` + đổi `run_inference` sang dùng bundle
- [x] 3. `health.py`: báo trạng thái bộ LFP
- [x] 4. Tests — 8 test mới (`TestChemistryArtifactSelection` ×3, `load_lfp_models` ×4, FTZ ×1)
- [x] 5. `pytest tests/ -q`: **547 passed**; ruff không thêm lỗi mới (6 lỗi E402/F401 có sẵn)

### Kết quả

**Selection hoạt động thật** — cùng 1 payload pack LFP 4S (cycle 900):

| Request | artifact_set | model_version | SOH | health_stage |
|---------|--------------|---------------|-----|--------------|
| `chemistry=None` | NASA | 1.6 | 97.19% | **Healthy** |
| `chemistry="LFP"` | LFP | 2.0-lfp | 85.13% | **Degrading** |

Đây đúng là lỗi mà bước này sửa: trước đó pin LFP đang suy giảm bị model NASA chấm là "Healthy".
`cycle_count_norm` đi kèm đúng bộ weight (NASA 200 / LFP 2300).

### 🚀 Phát hiện ngoài kế hoạch — `torch.set_flush_denormal(True)`

Khi benchmark, LFP p95 = **101.7ms → VƯỢT SLA <100ms**. Truy nguyên: cùng kiến trúc, cùng
79.467 tham số, cả 2 đều eager (torch.compile fail trên Windows) — chênh lệch chỉ đến từ **giá
trị trọng số** sinh ra số subnormal. x86 xử lý subnormal bằng microcode, chậm hơn hàng bậc, và
vòng lặp SSM (h nhân dồn qua 30 bước × 10 mẫu MC Dropout) sinh ra chúng hàng loạt.

`torch.set_flush_denormal(True)` trong `load_models()`:

| | avg trước | avg sau | p95 trước | p95 sau |
|---|---|---|---|---|
| NASA | 51.0 ms | **21.2 ms** | 70.8 ms | **24.6 ms** |
| LFP | 73.0 ms | **26.5 ms** | 101.7 ms (FAIL) | **30.6 ms** (PASS) |

**Dự đoán không đổi một chút nào** — cùng seed cho kết quả bit-identical (chênh lệch max
0.000000% qua 8 lần MC Dropout, trên **cả hai** bộ artifact). Subnormal < 1.2e-38, quá nhỏ để
dịch được một phần trăm SOH. Nên đây là tăng tốc thuần, không đánh đổi độ chính xác.

> ⚠️ Đây là thay đổi **ngoài scope plan** vì nó chạm cả đường NASA production. Lý do vẫn làm:
> (a) nếu không có nó thì chính việc wire LFP vừa làm sẽ vỡ SLA, (b) đã chứng minh không đổi
> kết quả, (c) 1 dòng. Nếu bạn muốn tách ra thành issue riêng thì nói, tôi revert khỏi commit này.

### Còn lại sau bước này — đã xử lý 2/3

**✅ Ngưỡng anomaly cho iso-forest LFP — KHÔNG cần sửa (đo được, không phải đoán).**
`decision_function = score_samples - offset_`, mà `offset_` được hiệu chỉnh từ `contamination`.
Hai forest đo ra gần như trùng nhau:

| | n_est | contamination | max_samples | `offset_` |
|---|---|---|---|---|
| NASA v1.6 | 100 | 0.1 | 256 | −0.553905 |
| LFP v2.0 | 100 | 0.1 | 256 | −0.551829 |

Lệch 0.002 → hai forest **cùng thang điểm**, nên ngưỡng −0.1/−0.3 mang cùng ý nghĩa cho cả hai.
Lo ngại "LFP có phân phối score riêng" của tôi là thừa.

**✅ `scripts/preprocess.py` (NASA) bug #10 — đã thêm `--soc-mode`, cố ý KHÔNG đổi mặc định.**

Xác nhận NASA dính đúng bug: `compute_soc_percent(raw_win[:, 1], raw_win[:, 3])` gọi trên lát
30 dòng → mọi window đều bắt đầu 100%. Đo trên chu kỳ xả NASA mô phỏng:
`window` → range [0.919, 1.000] (biến thiên 0.081) vs `cycle` → [0.169, 1.000] (biến thiên 0.831).

**Mặc định giữ `window`** — đây là quyết định quan trọng: `train.py` ghi ra
`soh_mamba_v{MODEL_VERSION}.pth`, nên nếu đổi mặc định thì **một lần chạy lại bình thường sẽ ghi
đè artifact v1.6 đang ship bằng ngữ nghĩa KHÁC dưới CÙNG số version** — đúng kiểu silent mismatch
mà các version assert sinh ra để chặn. Verify: mặc định cho kết quả **byte-identical** với
`soc_mode="window"`.

Muốn sửa thật thì chạy `--soc-mode cycle` **kèm bump `MODEL_VERSION`**. `soc_mode` được ghi vào
metadata `scaler.pkl` để artifact tự khai báo nó sinh ra bằng ngữ nghĩa nào.

**⏳ Còn lại: đặc trưng dQ/dV** — đòn bẩy độ chính xác lớn nhất, cần đổi contract 57-dim + feature
path riêng theo chemistry trong `inference.py`. Cần plan riêng.


## Bug thứ 12 (2026-07-31) — `pack_config` bị bỏ rơi trên đường Prescribe

**Audit nhánh trước khi ship, phát hiện lỗi phá cả GH-67 Mức 1 (đã merge PR #102) lẫn Mức 2.**

`PrescribeRequest.pack_config` được **cả 2 transport chấp nhận** nhưng `run_prescription()` chỉ
nhận `n_series`; `chemistry` và `capacity_ah` bị **âm thầm vứt đi** trước khi tới `run_inference`:

```python
# orchestrator.py — TRUOC khi sua
prediction_result = run_inference(readings, n_series=n_series, battery_id=battery_id)
```

Hệ quả trên đường **Prescribe** — chính là đường `docs/overall.md` §1 bảo BE dùng cho **mọi**
use-case tạo/enrich ticket:

| Tính năng | Trạng thái trước fix |
|---|---|
| Voltage profile theo chemistry (Mức 1) | ❌ pack LFP nhận ngưỡng NMC → cảnh báo giả / bỏ sót overcharge |
| Chuẩn hóa dòng theo C-rate `capacity_ah` (Mức 1) | ❌ không áp dụng |
| Chọn artifact set theo chemistry (Mức 2) | ❌ luôn dùng weight NASA |

Đường `Predict` thì đúng (`grpc_server.py:257` có truyền `chemistry`), nên lỗi chỉ lộ ra ở đúng
đường BE được khuyến nghị dùng — kiểu lỗi khó thấy nhất.

**Bug đi kèm: `cache_key` (GH-84) cũng thiếu `pack_config`.** Key chỉ gồm
`battery_id/readings/enrich/agentic/ticket_history`. Nghĩa là pack 4S và 1S cùng readings dùng
chung 1 cache entry, và sau khi thêm `chemistry` thì một request LFP có thể được trả về **kết quả
cache của NMC**. Đây là lỗi có sẵn, độc lập với chuyện chemistry.

**Đã fix:**
- `run_prescription()` + `_run_prescription_uncached()`: thêm `chemistry`/`capacity_ah`, forward
  xuống `run_inference`.
- `observability.cache_key()`: thêm `n_series`/`chemistry`/`capacity_ah` vào payload hash.
- `routers/prescribe.py` + `grpc_server.py`: forward đủ 3 field từ `pack_config` (parity 2 transport).
- 5 test hồi quy mới trong `tests/test_hybrid_prescription.py::TestPrescribePackConfigForwarding`:
  chemistry/capacity tới được `run_inference`; mặc định không đổi khi không có `pack_config`;
  request LFP **không** bị trả cache của NMC; cache vẫn hit khi `pack_config` giống hệt;
  `cache_key` phân biệt được từng field.

`pytest tests/ -q`: **552 passed**. ruff trên các file đã sửa: **1 lỗi, y hệt bản đã commit**
(có sẵn, không phải do thay đổi này).


## Bug thứ 13 (2026-07-31) — artifact `soc_mode='cycle'` + payload 3/4 cột = lệch phân bố ngầm

Mặt còn lại của bug #10. Model LFP được train với `soc_mode=cycle` (soc trải ~100% → ~9% suốt
đoạn xả), nhưng nhánh fallback của `_append_derived_features()` khi payload chỉ có 3/4 cột lại
tính soc **window-local** — luôn bắt đầu 100%, dải ~[0.91, 1.0].

| Payload | soc lúc inference | Khớp với LFP artifact? |
|---------|-------------------|------------------------|
| 6 cột (BE default) | SOC thật BE gửi, ~[0.09, 1.0] | ✅ |
| 3/4 cột | window-local, ~[0.91, 1.0] | ❌ lệch, không lỗi nào raise |

Không thể sửa bằng cách tính đúng: `run_inference` **stateless**, chỉ có 1 window 30 dòng nên
không thể dựng lại vị trí trong toàn đoạn xả.

**Đã fix — fail-fast, dựa trên metadata chứ không hardcode:**
- `preprocess_lfp.py` đã ghi `soc_mode` vào `scaler_lfp.pkl`; `model_loader` giữ lại thành
  `lfp_soc_mode` (default `"window"` để artifact cũ vẫn chạy).
- `_Artifacts` mang thêm `soc_mode`; `_append_derived_features()` **raise** khi
  `soc_mode == "cycle"` mà payload < 6 cột, kèm thông báo chỉ rõ phải gửi payload 6 cột.
- 3 test mới `tests/test_inference.py::TestSocModeGuard`: cycle-mode reject 4 cột / accept 6 cột
  (và lấy đúng soc của BE, không phải ước lượng), window-mode vẫn nhận 4 cột (back-compat NASA).

## ⚠️ Đã phát hiện, CHƯA sửa — mã lỗi sai contract (cần bạn quyết định)

`docs/overall.md` §11 ghi: *"Input sai (window≠30, **feature count sai**, out-of-range, NaN) →
`INVALID_ARGUMENT` / 422"*. Nhưng thực tế `grpc_server.py:261` bắt `except Exception` rồi
`abort(INTERNAL)`, nên **mọi** `ValueError` từ `run_inference` — kể cả lỗi input của client như
feature-count mismatch (`_align_features`) và guard `soc_mode` mới — đều báo `INTERNAL`/500.
REST cũng không có handler nên thành 500.

Đây là **lệch giữa tài liệu và code, có sẵn từ trước**, không phải do các thay đổi ở trên.

**Chưa sửa vì đây là quyết định về contract API đang chạy, không phải bug rõ ràng:** map
`ValueError → INVALID_ARGUMENT` sẽ đổi hành vi của các case đang tồn tại (BE có thể đang bắt theo
`INTERNAL`), và ngược lại có rủi ro che một `ValueError` nội bộ thật thành lỗi client. Cách sạch
nhất là tạo exception type riêng cho lỗi input rồi map type đó — nhưng đó là refactor nên cần
issue riêng.


## Bộ test full-case + phát hiện về độ trễ (2026-07-31)

Thêm `scripts/e2e_full_test.py` — chạy ma trận kịch bản thật qua gRPC wire, assert kết quả, chạy
ca lỗi, rồi đo tốc độ. Khác 2 script đã có: `benchmark_grpc.py` chỉ đo tốc độ với payload **4 cột
ngẫu nhiên không có `pack_config`** nên **chưa bao giờ chạm đường chemistry/LFP**;
`grpc_client_demo.py` chỉ demo, không assert.

Suite đã bắt được 3 thứ ngay lần chạy đầu:

**1. Kịch bản test yếu.** Hai ca "pack LFP khoẻ" và "pack LFP mòn" ban đầu đều ra SOH 100.00% vì
cùng rơi vào vùng model bão hoà (V/cell ≥ 3.25 → raw output ~102%, bị clip). Test không phân biệt
được gì. Đã đổi sang cặp điện áp nằm ngoài vùng đó.

**2. Đo `Prescribe` sai.** Dùng lại y hệt request nên toàn ăn cache idempotency (GH-84) → 0.6ms,
con số vô nghĩa. Đã đổi `battery_id` mỗi vòng.

**3. 🚨 Đường LFP vượt SLA P1 ở p95** — đo với server chạy **tiến trình riêng** (không tranh GIL):

| | p50 | p95 | SLA <100ms |
|---|---|---|---|
| direct `run_inference` NASA | 20.3ms | **23.3ms** | ✅ |
| direct `run_inference` LFP | 25.6ms | **29.1ms** | ✅ |
| gRPC Predict NASA | 48.6ms | 74.2ms | ✅ |
| **gRPC Predict LFP** | 69.7ms | **153.8ms** | ❌ |
| **gRPC Prescribe LFP** | 68.7ms | **159.7ms** | ❌ |

Bản thân pipeline model rất nhanh (p95 23–29ms) và **không có đuôi**. Toàn bộ vấn đề nằm ở tầng
phục vụ. Đã loại 2 giả thuyết bằng đo đạc:
- **Không phải do xen kẽ 2 bộ artifact**: chạy xen kẽ NASA↔LFP trực tiếp cho p95 29.3ms.
- **Không phải `torch.compile` recompile**: `torch.compile` không được dùng, 0 lần recompile.
- **Không phải tranh GIL in-process**: server tiến trình riêng vẫn p95 153.8ms.

**Chưa giải thích được:** vì sao qua gRPC đường LFP cộng thêm ~125ms ở p95 trong khi NASA chỉ
thêm ~51ms, dù hai đường đi qua **cùng** transport và pipeline trực tiếp chỉ chênh nhau 6ms.
`p50` của LFP (69.7ms) vẫn trong ngưỡng — **vấn đề nằm ở đuôi phân bố**. Cần điều tra trước khi
cho traffic P1 đi qua đường LFP.


## Tối ưu độ trễ (2026-08-01) — p95 đường LFP giảm 53%, về dưới SLA

### Truy nguyên nhân bằng đo đạc, loại 4 giả thuyết sai

| Giả thuyết | Cách bác bỏ |
|---|---|
| Tầng gRPC/serialization chậm | Response có sẵn `metadata.inference_ms`: round-trip p95 157.9ms vs server-side 156.8ms → **transport chỉ 1.1ms** |
| Xen kẽ 2 bộ artifact gây thrash | Chạy xen kẽ NASA↔LFP trực tiếp: p95 29.3ms |
| `torch.compile` recompile | Không dùng compile, 0 lần recompile |
| Tranh GIL do server in-process | Server tiến trình riêng vẫn p95 153.8ms |

### Nguyên nhân thật: mọi thread KHÁC main thread đều chậm

Cùng một hàm `run_inference`, chỉ khác thread gọi:

```
main thread                      p50= 26.7ms  p95=  31.9ms
threading.Thread (thuong)        p50= 65.5ms  p95= 149.4ms
ThreadPoolExecutor worker        p50= 63.4ms  p95= 158.1ms
```

Không phải chi phí submit/wait (chạy nguyên vòng lặp *bên trong* worker vẫn chậm). `cProfile`
trên worker thread cho thấy `_selective_scan` 14.8→36.5ms và `torch._C._nn.linear` (13 lần mỗi
inference) ngốn 30ms — tức **chi phí thiết lập vùng song song của từng op nhỏ tăng mạnh trên
thread phụ**, và biến động lớn (nên đuôi p95 nặng).

Giảm `torch.set_num_threads` KHÔNG cứu được (1 thread → p50 153ms) vì model vẫn hưởng lợi từ
song song; vấn đề là **số lượng op nhỏ**, không phải mức song song.

### Cách sửa: chọn nhánh scan theo thread

`MambaBlock._selective_scan` có sẵn 2 nhánh — vòng lặp Python 30 bước (L≤32) và chunked scan
vector hoá (L>32). Lý do gốc pin L≤32 vào vòng lặp là "tránh graph break cho `torch.compile`",
nhưng **compile không hề được bật** trên đường này. Đo cả hai:

| | main p50/p95 | worker p50/p95 |
|---|---|---|
| vòng lặp tuần tự | **24.2 / 29.5 ms** | 66.6 / **167.2 ms** |
| chunked vector hoá | 36.8 / 42.5 ms | 70.3 / **76.8 ms** |

Mỗi nhánh thắng ở một ngữ cảnh, nên điều kiện đổi thành
`if L <= 32 and threading.current_thread() is threading.main_thread()`. gRPC và FastAPI **đều**
dispatch handler lên thread pool → đường phục vụ luôn lấy nhánh chunked; train/eval và script
batch chạy main thread nên giữ vòng lặp nhanh hơn.

**Output bit-identical** — lệch 0.000000 %SOH trên dải quét 5 điểm điện áp (forward
deterministic, eval mode, không MC Dropout). Chỉ đổi lịch thực thi, không đổi phép tính.

### Kết quả

| | trước | sau |
|---|---|---|
| Predict LFP p95 | 172.9ms ❌ | **81.5ms** ✅ |
| Prescribe LFP p95 | 172.8ms ❌ | **76.4ms** ✅ |
| Predict NASA p95 | 67.0ms | **50.9ms** |
| Prescribe NASA p95 | 78.2ms | **52.4ms** |

`pytest tests/ -q`: 555 passed. `scripts/e2e_full_test.py`: TẤT CẢ PASS.
