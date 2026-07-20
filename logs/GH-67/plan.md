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

`pytest tests/ --cov=src`: 492 passed, coverage 92%. `scripts/benchmark_grpc.py`: PASS.
