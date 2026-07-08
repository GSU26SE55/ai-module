# Plan — GH-88: Optimize SOH v1.6 — fix coverage gap 4°C high-SOH + weighted loss

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-07-05
- **Issue:** #88 — https://github.com/GSU26SE55/ai-module/issues/88
- **Baseline:** v1.5 — test MAE 1.98% / RMSE 2.38% (B0048 held-out, 4°C)
- **Target:** MAE < 1.5% (thực tế) · MAE & RMSE < 1% (stretch) · hết bias hàng loạt vùng 80%

## Root cause (verified 2026-07-05 từ metadata.csv)

Train 4°C (B0041/45/53/54/55/56) chỉ phủ SOH **0–67.2%**; val/test (B0046/47/48) lên tới **86.4%**.
Vùng "4°C + SOH 67–86%" không tồn tại trong train → model ngoại suy lệch xuống ở đúng vùng ngưỡng
EOL 80% của test (verify GH-86: true 82.9% → pred 71–79, cả 10 MC samples < 80).

## Levers (ablation từng bước — đo riêng từng cái)

- **A1 — Split rebalance:** `VAL_IDS = ["B0046", "B0047"]` → chuyển **B0047 sang TRAIN_IDS**
  (4°C, SOH 0–83.7%, 72 cycles). Val còn B0046 (4°C, SOH 0–86.4%). **TEST B0048 nguyên vẹn.**
  Sửa duy nhất `scripts/preprocess.py` (source of truth theo rules).
- **A2 — Balance-band weighting:** option mới `--balance-bands` trong `train.py` — weight mỗi window
  ∝ nghịch đảo tần suất bin (temp_domain × SOH band 10%), clip weight max 5.0 tránh outlier chi phối.
  Khác `--weighted-loss` hiện có (chỉ upweight SOH<80): cái này cân cả vùng hiếm SOH cao 4°C.
  Default OFF — bật qua flag, không đổi hành vi cũ.
- **A3 (dự phòng, chỉ khi A1+A2 chưa đạt):** `--jitter`/`--swa` (đã có sẵn flag) → sweep nhỏ.
  KHÔNG đổi architecture trong ticket này.

## Ràng buộc
- **Train Kaggle only** (T4 x2 — không P100). Preprocess chạy local được (CPU, nhanh, không phải train).
- Seed 42, window=30, architecture v1.x giữ nguyên → bump **MODEL_VERSION 1.5→1.6**,
  SCALER_VERSION 1.2→1.3, FEATURE_SCALER_VERSION 1.4→1.5 (scaler refit trên train set mới).
- Retrain xong: commit **4 artifacts cùng 1 commit** (model + scaler + feature_scaler + isolation_forest)
  — user tự commit.
- Latency <100ms không đổi (không đụng inference path).

## ⚠️ Ảnh hưởng NCKH — cần chốt với GVHD
Đổi split = đổi protocol thí nghiệm → Table 1/2 paper. Phải chốt **TRƯỚC khi chạy LOBO (GH-68)**.
Câu justify cho GVHD: "train set thiếu hoàn toàn vùng nhiệt độ-SOH mà test yêu cầu → đo generalization
không công bằng; chuyển 1/2 pin val sang train, test vẫn held-out 100%" + ADR ghi lại.

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/preprocess.py` | modify | A1: B0047 VAL→TRAIN + comment justification |
| `src/core/config.py` | modify | bump MODEL 1.6 / SCALER 1.3 / FEAT_SCALER 1.5 |
| `scripts/train.py` | modify | A2: `--balance-bands` (+ helper tính weight, áp dụng path window-30) |
| `notebooks/kaggle_train_v16.ipynb` | create | 3 run ablation: baseline(re-run)/A1/A1+A2 — user chạy Kaggle |
| `tests/test_training_utils.py` hoặc test hiện có | modify | unit test hàm tính balance-band weights (không train) |
| `logs/GH-88/ablation.md` | create | bảng MAE/RMSE tổng + per-band (75–85%) từng run |
| `docs/adr/000X-split-rebalance-b0047.md` | create | justification đổi split + impact NCKH |
| `.claude/rules/tech/ai.md`, `CLAUDE.md` | modify | bảng split 24/1/1 (SAU khi GVHD chốt) |
| `models/weights/*_v1.6.*` | output | user train Kaggle + commit |

## Workflow thực thi (tuân thủ no-local-training)

```
[tôi]  B1 code: split + versions + preprocess chạy local → verify coverage train chứa 67–83.7% @4°C
[tôi]  B2 code: --balance-bands + unit test weight (CPU, không train)
[tôi]  B3 notebook Kaggle v1.6 (3 run ablation, in per-band MAE + 16-window case 82.9%)
[user] B4 chạy Kaggle (T4 x2) → tải artifacts + log về
[tôi]  B5 đánh giá: ablation.md + verify bias case + benchmark latency + full pytest
[user] B6 commit artifacts + code; /kltn-reviewcode → /kltn-test 88 → ship
```

## Steps
- [x] B1: A1 split + version bumps + re-preprocess local — train 18,224 windows (24 pin, B0047 in),
      val 768 (B0046), versions 1.3/1.5 truyền đúng
- [x] B2: A2 `--balance-bands` + per-band MAE report trong train.py + 5 unit tests (pass);
      full suite 274 passed / 2 skipped (test_model_loader chờ artifact v1.6 — skipif có chủ ý)
- [x] B3: `notebooks/kaggle_train_v16.ipynb` — 2 run A1/A2, chọn theo val MAE, đóng gói zip
- [x] B4: user train Kaggle (T4 x2), đem kết quả về — merged dev qua PR #93 (2026-07-07)
- [x] B5: ablation.md (`logs/GH-88/ablation.md`) + verify 16 windows 82.9% + coverage ≥85% —
      MAE 1.34%/RMSE 1.84% đạt target chính (<1.5%), stretch <1% và bias vùng 80-90% chưa
      hết hẳn nhưng ghi nhận là known limitation (n=16, không train thêm)
- [ ] B6: ADR + cập nhật rules table (sau GVHD chốt) → review → test → ship

## Success criteria
| Tiêu chí | Verify |
|---|---|
| Train 4°C phủ SOH tới ~83.7% | log preprocess (per-battery range) |
| MAE < 1.5% (stretch <1%) test B0048 | checkpoint metadata + ablation.md |
| Per-band MAE 75–85% giảm rõ so 4.5–11 điểm hiện tại | ablation.md |
| 16 windows true 82.9% không còn pred <78 hàng loạt | script verify (như GH-86) |
| Latency <100ms, coverage ≥85%, seed 42 | benchmark + pytest |
