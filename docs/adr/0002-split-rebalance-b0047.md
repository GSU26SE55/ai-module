# ADR 0002 — Split rebalance: B0047 val → train (GH-88, model v1.6)

**Ngày:** 2026-07-05 · **Trạng thái:** Accepted — user tự chốt 2026-07-08 (không qua GVHD) · **Issue:** #88

## Bối cảnh

Model v1.5 đạt test MAE 1.98% / RMSE 2.38% (B0048, 4°C held-out) nhưng có **bias hệ thống** tại
vùng quan trọng nhất: windows true SOH 82.9% bị predict 71–79 (lệch 4–11 điểm, cả 10 MC Dropout
samples < 80) → health_stage flip sang "End Of Life" tại đúng ngưỡng EOL 80% (phát hiện khi verify GH-86).

Root cause (verified từ `metadata.csv` NASA, 2026-07-05):

| Nhóm pin 4°C | SOH range |
|---|---|
| Train: B0041/45/53/54/55/56 | 0 – **67.2%** |
| Val: B0046, B0047 | 0 – 86.4% / 0 – 83.7% |
| Test: B0048 | 0 – 82.9% |

Vùng **4°C × SOH 67–86%** không tồn tại trong train — model buộc ngoại suy tại đúng dải test yêu cầu
và ngoại suy lệch xuống. Đây là lỗ hổng data coverage cấu trúc: không loss function, hyperparameter
hay uncertainty flag nào bù được dữ liệu không có.

## Quyết định

Chuyển **B0047** (4°C, SOH 0–83.7%, 69 cycles sau filter) từ `VAL_IDS` sang `TRAIN_IDS`
trong `scripts/preprocess.py` (nguồn duy nhất của split theo `rules/tech/ai.md`):

- Split mới: **24 train / 1 val (B0046) / 1 test (B0048)**
- Val còn B0046 — vẫn 4°C, SOH 0–86.4%, phủ trọn dải test → early-stopping signal giữ nguyên domain
- **Test B0048 không đụng tới** — chưa từng xuất hiện trong bất kỳ quyết định train/tuning nào,
  cross-battery generalization vẫn được đo trung thực
- Version bump: MODEL 1.5→1.6, SCALER 1.2→1.3, FEATURE_SCALER 1.4→1.5 — retrain bắt buộc (Kaggle)

Kèm theo (cùng GH-88): option `--balance-bands` trong `train.py` — weight nghịch đảo tần suất bin
(temperature × SOH band) để vùng hiếm không bị khối 24°C mid-SOH nuốt trong loss. Ablation A1 (split
only) vs A2 (split + balance-bands) đo riêng, chọn model theo **val MAE** (không dùng test để chọn).

## Hệ quả

- **NCKH:** đổi protocol thí nghiệm → Table 1/2 của paper dùng split mới thống nhất (24/1/1).
  User tự chốt quyết định này 2026-07-08 (theo quyết định chung: tự duyệt mọi thứ, không qua GVHD
  — deadline nộp 20/7). Justification: "train thiếu hoàn toàn vùng temperature×SOH mà test yêu cầu →
  điểm số đo được phản ánh extrapolation gap chứ không phải năng lực model; rebalance giữ test 100%
  held-out." LOBO (GH-68, `scripts/experiment_nowcast_lobo.py`) không bị ảnh hưởng — fold list của
  script này lấy trực tiếp từ `metadata.csv` (`available_batteries`/`batteries_at_temp`), không đọc
  `TRAIN_IDS`/`VAL_IDS` của `preprocess.py`, nên đổi split ở đây không đòi hỏi chạy lại LOBO.
- Bảng split trong `.claude/rules/tech/ai.md` + `CLAUDE.md` đã cập nhật (2026-07-08).
- Val chỉ còn 1 pin (768 windows) — chấp nhận được: cùng domain 4°C, đủ lớn cho early stopping;
  trade-off đã cân nhắc so với việc mất hẳn coverage vùng 80% trong train.
- Artifacts v1.6 (model + scaler + feature_scaler + isolation_forest) commit cùng 1 commit sau khi
  train Kaggle (notebook `notebooks/kaggle_train_v16.ipynb`).
