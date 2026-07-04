# Plan — GH-70: [NCKH] Anomaly evaluation — ground truth + scripts/eval_anomaly.py → Table 5

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-04
- **Issue:** #70 — [NCKH] Anomaly evaluation — định nghĩa ground truth EOL-based + scripts/eval_anomaly.py → Table 5 (F1 > 0.80)
- **Sprint:** NCKH paper (không milestone) — deadline: chốt định nghĩa với GVHD **trước 8/7**, có số **trước 13/7**

## Mục tiêu
Định nghĩa proxy ground truth cho anomaly (NASA dataset không có nhãn), viết `scripts/eval_anomaly.py` chạy IsolationForest trên features có sẵn, xuất **Table 5** (Precision/Recall/F1 trên val B0046/47 + test B0048) và **Figure F6** (histogram anomaly score + ngưỡng −0.1/−0.3) cho bài báo NCKH.

## ⚠️ Phát hiện quyết định approach (đã verify trên `data/processed/*.pt`)

Định nghĩa gốc trong issue — "cycle có SOH < 80% (EOL) = anomalous" — bị **degenerate** trên split hiện tại:

| Split | Windows | % windows SOH < 80% |
|-------|---------|---------------------|
| Train (23 pin) | 17,456 | 63.3% |
| Val (B0046/47, 4°C) | 1,536 | **97.9%** |
| Test (B0048, 4°C) | 768 | **97.9%** |

Pin 4°C val/test đã dưới EOL gần như từ đầu chuỗi đo (SOH ~30–61%). Với ~98% positive: classifier "luôn báo anomalous" đạt F1≈0.99 (vô nghĩa), còn IsolationForest contamination=0.1 chỉ flag ~10% → recall ~0.1. Cả hai chiều đều làm Table 5 không dùng được về mặt học thuật.

→ **Phương án chính (đã chốt với dev 4/7, chờ GVHD duyệt): nhãn "suy thoái nhanh" per-battery** thay vì ngưỡng EOL tuyệt đối. Script vẫn hỗ trợ chạy cả EOL-based để so sánh trong buổi trao đổi với thầy.

## Định nghĩa proxy label đề xuất (mang đi chốt với GVHD)

**Primary — rate-based (per-battery rapid degradation):**
1. Mỗi pin: SOH theo cycle (Capacity/2.0×100), làm mượt rolling median (window 5 cycles).
2. Tốc độ suy thoái cục bộ tại cycle i: `r_i = −(SOH[i+2] − SOH[i−2]) / 4` (%SOH/cycle, central difference; biên dùng one-sided).
3. Ngưỡng θ = **percentile 90 của phân bố r trên train set** — align với contamination=0.1 của IsolationForest (nhãn dương ≈10% train theo construction).
4. Cycle anomalous ⇔ `r_i > θ`. Mọi window trong cycle kế thừa nhãn của cycle.

Viết được 2–3 câu cho Section 3.5: *"Since the NASA dataset lacks fault annotations, we define a proxy anomaly label: a cycle is anomalous if its locally smoothed degradation rate exceeds the 90th percentile of the training-set rate distribution — aligned with the Isolation Forest contamination prior of 0.1. This captures the rapid-degradation regime of each cell rather than an absolute SOH threshold, which would be degenerate on the low-temperature val/test cells (98% of windows below 80% SOH)."*

**Secondary — EOL-based (SOH < 80%):** giữ đúng đề xuất gốc của issue, chạy song song để báo cáo trung thực + làm bằng chứng vì sao phải đổi định nghĩa.

**Limitations (ghi vào bài):** cả hai đều là proxy label suy ra từ capacity fade, không phải fault annotation thật; kết quả đo khả năng IsolationForest tách chế độ suy thoái, không phải phát hiện lỗi sensor thực địa.

## Scope
**Trong scope:**
- `scripts/eval_anomaly.py` — gán nhãn (rate-based + eol-based), fit IsolationForest trên train features, tính P/R/F1 val+test, xuất Table 5 + Figure F6
- Threshold sweep **chỉ trên val** nếu F1 < 0.80 (không nhìn test), báo cáo trung thực cả số default lẫn số tuned
- Unit test cho hàm gán nhãn + chọn ngưỡng (`tests/test_eval_anomaly.py`)
- Lưu kết quả `logs/nckh/anomaly/`

**Ngoài scope:**
- Không retrain Mamba/scaler, không đổi split, không đổi hyperparameter IsolationForest (contamination=0.1, n_estimators=100, seed 42 — cite Liu et al. 2008)
- Không sửa `src/` production code (mapping −0.1/−0.3 giữ nguyên)
- Không viết text bài báo (chỉ xuất số liệu + câu định nghĩa/limitations draft trong results)
- Synthetic fault injection — chỉ làm nếu GVHD yêu cầu (issue mới)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/eval_anomaly.py` | create | ~120 dòng (issue ước 50 — thêm phần label rate-based + figure). Seed 42 |
| `tests/test_eval_anomaly.py` | create | Test hàm label (rate/eol) + hàm chọn ngưỡng trên val |
| `logs/nckh/anomaly/results.json` | output | P/R/F1 mỗi split × mỗi định nghĩa × mỗi ngưỡng, label balance |
| `logs/nckh/anomaly/table5.md` | output | Bảng paste thẳng vào paper |
| `logs/nckh/anomaly/figure_f6.pdf` + `.svg` | output | Histogram score val/test + vline −0.1/−0.3, font ≥8pt, colorblind-safe |

## Approach
- **Data:** dùng `X_feat` (57-dim, đã StandardScaler) có sẵn trong `data/processed/{train,val,test}.pt` — không recompute features. Cycle identity không lưu trong `.pt` → tái tạo bằng cách import `load_cycles` từ `scripts/preprocess.py` (thứ tự deterministic), replay công thức số window mỗi cycle `n_win = (T−30)//30 + 1`; **assert tổng windows khớp** với shape `X_feat` từng split trước khi gán nhãn.
- **Model:** fit `IsolationForest(contamination=0.1, n_estimators=100, random_state=42)` trên train `X_feat` — giống hệt `scripts/train.py` (cùng data + seed → tương đương artifact `isolation_forest_v1.5.pkl`). Fit local vài giây, không cần Kaggle.
- **Prediction rules báo cáo trong Table 5:** score = `decision_function`; 3 rule: `score ≤ −0.1` (Warning trở lên), `score ≤ −0.3` (Anomaly), `predict() == −1` (contamination cutoff). Nếu tất cả F1 < 0.80 → sweep ngưỡng trên **val**, chọn best-F1, report thêm cột "tuned" trên test.
- **Figure F6:** matplotlib histogram score (val + test overlay), vlines −0.1/−0.3, xuất PDF + SVG.
- **In label balance mỗi split** — guard: nếu định nghĩa rate-based vẫn cho >90% một class trên val/test → dừng, escalate cho GVHD (không cố tune cho đẹp).

## Edge Cases
- Thiếu `data/processed/*.pt` hoặc `data/raw/nasa/cleaned_dataset/` → fail sớm với message chỉ rõ chạy `scripts/preprocess.py` trước
- Số window replay ≠ shape `X_feat` → assert với message chi tiết (split, expected, actual) — chống lệch thầm lặng giữa nhãn và features
- Pin quá ngắn (<5 cycles) cho rolling median → dùng min_periods=1, one-sided diff ở biên
- F1 < 0.80 sau tuning → báo cáo trung thực cả 2 số, KHÔNG nhìn test khi tune (issue yêu cầu rõ)
- Label balance degenerate với cả rate-based → dừng + escalate GVHD

## Acceptance Criteria
- [ ] **GVHD duyệt định nghĩa label trước khi chạy số chính thức** (BƯỚC 1 của issue — deadline 8/7)
- [ ] Table 5 đủ P/R/F1 trên val (B0046/47) + test (B0048), cả 2 định nghĩa label, ghi rõ class balance
- [ ] Định nghĩa label viết được thành 2–3 câu rõ ràng cho Section 3.5 (draft có sẵn trong plan + results)
- [ ] Figure F6 xuất PDF/SVG, có ngưỡng −0.1/−0.3
- [ ] Nếu F1 < 0.80: có bảng threshold sweep trên val + số tuned trên test, báo cáo cả hai
- [ ] Câu Limitations (proxy label) draft sẵn trong `logs/nckh/anomaly/results.json`/`table5.md`
- [ ] Chạy local < 1 phút, seed 42, `pytest tests/test_eval_anomaly.py` PASS

## Steps
- [x] **Bước 0 (GATE):** Mang phát hiện degenerate + 2 định nghĩa đi chốt với GVHD — GVHD đã duyệt định nghĩa rate-based per-battery — 2026-07-04
- [x] Bước 1: Viết hàm gán nhãn (rate-based per-battery + eol-based) + replay cycle→window mapping với assert — 2026-07-04
- [x] Bước 2: Fit IsolationForest trên train X_feat, tính score + P/R/F1 val/test theo 3 prediction rule — 2026-07-04
- [x] Bước 3: Threshold sweep trên val (F1 < 0.80 → đã tuning, val-only) → report tuned trên test — 2026-07-04
- [x] Bước 4: Vẽ Figure F6 (histogram + ngưỡng) → PDF/SVG — 2026-07-04
- [x] Bước 5: Xuất `logs/nckh/anomaly/{results.json, table5.md, figure_f6.pdf/svg}` — 2026-07-04
- [x] Bước 6: Unit test hàm label + hàm chọn ngưỡng; `ruff` + `pytest` PASS (7/7) — 2026-07-04

## Kết quả thực tế (2026-07-04) — ⚠️ F1 target KHÔNG đạt, cần trao đổi GVHD

Số chính thức trong `logs/nckh/anomaly/table5.md`. Tóm tắt:
- **Rate label (primary):** class balance đã hết degenerate (val 35.5% / test 20.6% positive) ✓, nhưng IsolationForest score gần như không tương quan với nhãn — F1 = 0.000 ở cả 2 ngưỡng documented (−0.1/−0.3), tuned trên val chỉ đạt **F1 val 0.525 / test 0.342** (< 0.80).
- **Nguyên nhân (đã verify, không phải bug):** score distribution val/test nằm hoàn toàn trong [−0.075, 0.22] — **không window nào chạm −0.1**, ngưỡng mapping production không bao giờ kích hoạt trên 4°C data. Train có đúng 10% score < 0 (contamination hoạt động đúng). IsolationForest phát hiện outlier trong feature space, không phát hiện chế độ suy thoái nhanh (temporal).
- **EOL label (secondary):** tuned F1 0.985/0.988 — con số đẹp nhưng là artifact của 97.9% positive (predict-all đạt tương đương), không dùng làm headline được.
- Threshold tuning chỉ trên val, không nhìn test — báo cáo trung thực cả default lẫn tuned theo đúng plan.

## Câu hỏi đã giải đáp
1. **GVHD đã duyệt định nghĩa chưa?** → Chưa. Plan viết trước kèm option analysis; implement chờ thầy duyệt (Bước 0 là gate).
2. **Định nghĩa label chính?** → Rate-based per-battery (suy thoái nhanh), vì EOL-based bị degenerate ~98% positive trên val/test 4°C (đã verify bằng số). EOL-based vẫn chạy song song làm secondary/bằng chứng.
3. **Fit lại hay load `isolation_forest_v1.5.pkl`?** → Fit lại trong script theo đúng chữ issue (cùng data + hyperparams + seed 42 → tương đương artifact); tránh phụ thuộc version pkl.
4. **Tune ngưỡng ở đâu?** → Chỉ trên val, không nhìn test — đúng yêu cầu issue, báo cáo trung thực cả hai số.
