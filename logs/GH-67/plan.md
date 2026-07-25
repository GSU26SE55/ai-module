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

### Việc còn lại
- [ ] Push round 2 + round 3 (cycle-stride, cycle_idx=j, TIMING, PHYSICAL_RANGES) rồi chạy lại
  Kaggle → kỳ vọng MAE cải thiện thêm nhờ kênh temperature/voltage hồi phục độ phân giải.
- [ ] Chemistry-aware artifact selection (vẫn chưa làm) — nhớ `LFP_CYCLE_COUNT_NORM` (2300),
  xem cảnh báo ở mục trên.
- [ ] Model LFP hiện CHƯA được wire vào inference — `chemistry=="LFP"` vẫn dùng artifact NASA.
