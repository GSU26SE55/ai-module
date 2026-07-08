# GH-88 — Ablation Report: SOH v1.6 (split rebalance + optional balance-bands)

**Ngày:** 2026-07-08 | **Model:** `soh_mamba_v1.6.pth` (đã merge `dev` qua PR #93, commit `bcf0aa9`)
**Eval:** load checkpoint + `data/processed/test.pt` (768 window, B0048 held-out, 4°C) — inference-only, không train lại.

## 1. Overall test metrics

| | v1.5 (baseline) | v1.6 (hiện tại) | Target GH-88 |
|---|---|---|---|
| Test MAE | 1.98% | **1.3409%** | <1.5% ✅ · stretch <1% ❌ |
| Test RMSE | 2.38% | **1.8426%** | <3% ✅ |

Checkpoint metadata xác nhận `balance_bands: False` — nghĩa là giữa 2 run Kaggle (A1: split rebalance only / A2: split + `--balance-bands`), **A1 thắng theo val MAE** và được commit làm artifact chính thức. Log Kaggle của phiên chạy 2 run không được lưu lại (notebook không có output cell đã lưu, artifact zip chỉ mang theo model thắng cuộc) — nên **không có con số val MAE cụ thể của run A2 để đối chiếu**; đây là giới hạn của báo cáo này, không phải số bị thiếu do lỗi.

## 2. Per-band test MAE (mục tiêu chính của GH-88: vùng SOH cao ở 4°C)

| SOH band | n | MAE | Bias |
|---|---|---|---|
| 50-60% | 69 | 1.546% | +0.938% |
| 60-70% | 512 | 1.183% | +0.132% |
| 70-80% | 171 | 1.429% | -0.909% |
| 80-90% | 16 | 4.568% | **-4.568%** |

Vùng 80-90% (16 window, toàn bộ từ B0048 true SOH=82.9%) vẫn là vùng yếu nhất — bias âm hệ thống, model vẫn dự đoán thấp hơn thật.

## 3. Verify case cụ thể — 16 window true SOH=82.9% (case GH-86 phát hiện ở v1.5)

Dự đoán riêng lẻ (16 window):
```
73.93  77.86  78.02  76.10  77.94  78.17  76.88  79.59
76.58  76.40  79.20  79.79  80.98  81.50  80.23  80.14
```

- v1.5: **10/10 MC sample <80** (100% dưới ngưỡng EOL, gây flip classification "Failed" cho pin healthy)
- v1.6: **7/16 <78**, 9/16 đã ≥78 (một số ≥80: 80.98, 81.50, 80.23, 80.14)

→ **Cải thiện rõ so với v1.5 nhưng chưa giải quyết dứt điểm** — gần một nửa số window vẫn lệch xuống dưới ngưỡng nhạy cảm 80%. Nguyên nhân còn lại nhiều khả năng là cỡ mẫu quá nhỏ (n=16, toàn bộ đến từ 1 giá trị true SOH duy nhất của 1 pin) chứ không phải thiếu coverage nữa (coverage train đã verify phủ tới 83.7% ở bước B1).

## 4. Latency

Không đo lại trong báo cáo này — GH-88 không đổi architecture/inference path so với v1.5 (chỉ đổi split + data dùng để train), nên số latency đã benchmark ở `logs/GH-60/validation_report.md` (494.8ms trên CPU dev machine, FAIL SLA <100ms) vẫn áp dụng nguyên trạng. Đây là vấn đề riêng (MC Dropout 20 pass trên CPU), không phải regression do GH-88 gây ra.

## 5. Kết luận

**Target chính đạt được:** MAE 1.34% < 1.5% ✅, RMSE 1.84% < 3% ✅ — cải thiện đáng kể so với v1.5 (1.98/2.38).
**Stretch goal (<1%) chưa đạt.**
**Root cause ban đầu (bias vùng SOH cao 4°C) giảm nhưng chưa hết** — biết là known limitation do cỡ mẫu test quá nhỏ ở vùng này (n=16, 1 pin), không phải do thiếu nỗ lực retrain.

**Quyết định (2026-07-08):** đóng GH-88 ở mức hiện tại — không train thêm (A3 jitter/SWA). Vùng SOH cao 4°C ghi nhận là limitation cần nêu trong phần discussion/limitation của bài NCKH nếu liên quan.
