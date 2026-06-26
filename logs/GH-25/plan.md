# Plan — GH-25: Optimize SOH prediction — đẩy MAE < 1% VÀ RMSE < 1% (sub-1% target)

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-06-26
- **Issue:** #25 — https://github.com/GSU26SE55/ai-module/issues/25
- **Sprint:** Sprint 4
- **Dev:** Nguyễn Phúc Duy (SE184821)

## Mục tiêu
Đẩy Mamba SOH predictor xuống **MAE < 1% VÀ RMSE < 1%** trên test set B0018 (30% cuối), train trên **Kaggle GPU**. Chặt hơn spec hiện tại (MAE<2%/RMSE<3%). Rào cản thật là **RMSE < 1%** — lỗi dồn ở vùng EOL + capacity regeneration spike của B0018 → hướng đi là **giảm variance lỗi**, không chỉ bias.

## Scope
**Trong scope (4 lever, đo ablation từng cái — thứ tự ROI):**
1. **Loss weighting / Huber** — đổi `MSELoss` → SmoothL1/Huber, hoặc weighted loss tăng trọng số vùng SOH thấp (EOL). Tấn công trực tiếp RMSE.
2. **Capacity regeneration handling** — phát hiện & làm mượt regeneration spike trong target (preprocess) hoặc augmentation phản ánh hiện tượng.
3. **TTA / ensemble sliding-window** — trung bình nhiều cửa sổ lúc inference để giảm variance → re-benchmark latency.
4. **Hyperparameter sweep** — lr schedule, dropout, batch, epochs/patience quanh cấu hình tốt (làm sau cùng).
- **Cho phép đổi kiến trúc** nếu loss/data chưa đủ → bump **v2.0 + ADR** (exception architecture freeze `ai.md`).
- Bảng ablation MAE/RMSE before-after từng lever cho hồ sơ KLTN.

**Ngoài scope / ràng buộc cứng:**
- Train **Kaggle GPU only** (không tuning CPU local).
- KHÔNG đổi train/val/test split (B0005/6/7 | B0018 70% | B0018 30%), window=30, seed=42.
- KHÔNG thêm ML framework ngoài PyTorch + scikit-learn.
- Inference latency vẫn < 100ms (P1 SLA) — benchmark lại sau optimize, đặc biệt khi bật TTA.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/train.py` | modify | `--loss` (mse/huber/weighted), `--augment`; log MAE+RMSE; giữ seed 42 |
| `scripts/preprocess.py` | modify | regeneration smoothing / augmentation cho target (nếu áp dụng ở data) |
| `src/models/soh_predictor.py` | modify | chỉ khi đổi kiến trúc → bump **v2.0** + cập nhật metadata |
| `src/services/inference.py` | modify | tùy chọn TTA/ensemble sliding-window (sau benchmark) |
| `docs/adr/00XX-soh-sub1pct-optimization.md` | create | ghi lever + exception architecture freeze + version bump |
| `logs/GH-25/ablation.md` | create | bảng so sánh MAE/RMSE từng lever |
| `models/weights/soh_mamba_v1.x\|v2.0.pth` | output | model mới + metadata version |
| `tests/test_soh_predictor.py` | modify | giữ precision/latency test; thêm regression metric |

## Approach
- Tiền đề: train trên Kaggle GPU ⇒ **dựa trên fp32 SSM scan của GH-9** (precision fix phải có trong code train, nếu không metric GPU chạy theo nhiễu fp16). Coi GH-9 là dependency must-land.
- Baseline lại MAE/RMSE GPU hiện tại, ghi số gốc vào `ablation.md`.
- Lần lượt: (1) Huber/weighted loss → (2) regeneration handling → đo riêng từng cái. Nếu RMSE vẫn >1% → (3) TTA/ensemble. Cuối cùng (4) sweep nhỏ.
- Nếu sau loss+data+TTA vẫn không đạt → cân nhắc đổi kiến trúc (v2.0 + ADR).
- Chốt model đạt cả 2 <1%, benchmark latency <100ms, viết ablation + ADR; commit 3 artifacts (model + scaler + isolation_forest) cùng commit.

## Edge Cases
- Weighted loss làm lệch vùng healthy → kiểm tra MAE không tăng ngược ở SOH cao.
- Regeneration smoothing quá tay → bóp méo ground-truth → giữ bản gốc để so, smoothing chỉ ở train target.
- TTA tăng latency → nếu >100ms thì TTA chỉ dùng cho batch P2/P3, P1 giữ single-window.
- Đổi kiến trúc → phải giữ contract `(x, x_feat)` cho inference + scaler tương thích, nếu không break `/predict`, `/prescribe`.
- Overfit B0018 nhỏ → theo dõi val/test gap, không tuning tới mức leak test.

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| Test MAE < 1.0% VÀ RMSE < 1.0% trên B0018 | log cuối `train.py` ACHIEVED |
| Lặp lại được (seed 42) | 2 run cùng seed → chênh < 0.05% (dựa GH-9) |
| Đạt trên Kaggle GPU | log Kaggle |
| Latency < 100ms | `pytest tests/test_inference.py` |
| Ablation đầy đủ | `logs/GH-25/ablation.md` có bảng từng lever |
| Đổi kiến trúc → v2.0 + ADR | file ADR tồn tại, 3 artifacts commit cùng commit |
| Coverage ≥ 85% | `pytest --cov=src` |

## Steps
- [ ] B1 Preprocess: regeneration smoothing/augmentation option (`preprocess.py`) — đo riêng
- [ ] B2 Model/training: thêm `--loss huber/weighted` vào `train.py`; baseline + ghi `ablation.md`
- [ ] B3 Inference: TTA/ensemble sliding-window option (`inference.py`) nếu RMSE còn >1%
- [ ] B4 Hyperparameter sweep nhỏ (lr/dropout/batch) — sau cùng
- [ ] B5 (nếu cần) đổi kiến trúc → bump v2.0 + ADR exception
- [ ] B6 Unit test + latency benchmark <100ms; `pytest --cov=src` ≥85% PASS
- [ ] B7 Train Kaggle GPU xác nhận MAE<1% & RMSE<1%; commit 3 artifacts + ablation + ADR

## Câu hỏi đã giải đáp
- **Train ở đâu?** → Kaggle GPU only, không tuning CPU local.
- **GH-9 dependency?** → GH-25 dựa trên fp32 SSM scan của GH-9 (must-land để metric GPU đáng tin).
- **Được đổi kiến trúc không?** → Có, nếu loss/data/TTA không đủ → bump v2.0 + viết ADR (exception `ai.md` freeze).
- **Lever ưu tiên?** → Cả 4, thứ tự ablation: Huber/weighting + regeneration trước → TTA → sweep.
