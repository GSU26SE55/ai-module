# Plan — GH-35: Enable EOL-weighted SmoothL1 loss for critical SOH region

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-07-01
- **Issue:** #35 — GH-XX(AI): Enable EOL-weighted SmoothL1 loss for critical SOH region
- **Sprint:** Sprint 4 (deadline 2026-07-11)
- **Priority:** P1 Critical

## Mục tiêu
Enable weighted loss function (already implemented) để upweight samples gần EOL (80% SOH) bằng 2–2.5×. 
Điều này giảm MAE trong vùng critical 75–85% SOH (nơi error predictions gây nguy hiểm an toàn), 
và cải thiện training stability qua SmoothL1 clipping.

Expected outcome: MAE ≤ 1.80%, RMSE ≤ 2.8% sau retrain.

## Scope
**Trong scope:**
- Modify `scripts/train.py` line 340, 420, 269: add `weighted_loss=True`, `eol_weight_scale=2.5` parameters
- Verify training logs show upweighted samples (weight > 1.0 near EOL)
- Retrain `train()` and `train_long()` functions
- Validate metrics: MAE ≤ 1.80%, RMSE ≤ 2.8%
- Test set outlier robustness: fewer > 3% errors
- Document EOL weight formula in `.claude/CLAUDE.md` or `CLAUDE.md`

**Ngoài scope:**
- Thay đổi architecture model
- Tuning lại hyperparameter khác (epochs, batch size, lr)
- Thêm feature preprocessing
- IoT pipeline (scope Sprint 8)

## Technical Approach
1. **Loss function:** `_soh_weighted_smooth_l1` đã implement (line 324) — enable nó thay vì MSELoss
2. **EOL weighting:** Samples có SOH 75–85% được upweight 2–2.5× (công thức: `weight = 1.0 + 1.5 * (1 - abs(soh - 80) / 5)` or similar)
3. **Training flow:** 
   - Load train data
   - Compute sample weights (based on SOH proximity to 80%)
   - Pass `weighted_loss=True, eol_weight_scale=2.5` to loss function
   - Monitor loss — gradient clipping từ SmoothL1 → stable training
4. **Validation:**
   - Check training logs: log sample weights, verify EOL samples get weight > 1.0
   - Compute metrics on test set: MAE, RMSE, per-SOH bucket error distribution
   - Verify fewer outliers (> 3% error) in 75–85% range

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `scripts/train.py` | modify | Line 269 (train()), 340/420 (train_long()) — add weighted_loss, eol_weight_scale params |
| `src/models/soh_predictor.py` hoặc `src/models/rul_predictor.py` | verify | `_soh_weighted_smooth_l1` function đã có sẵn |
| `CLAUDE.md` | modify | Document EOL weight formula + rationale (IEC 62619 reference) |
| `models/weights/soh_lstm_v*.pth`, `isolation_forest_v*.pkl`, `scaler.pkl` | create | Retrained artifacts |
| `logs/training/train_*.log` | create | Training logs (verify upweighting) |

## Edge Cases
- Samples far from EOL (< 50% SOH): weight ≈ 1.0 (no upweighting)
- Samples at exact EOL (80% SOH): weight = max (2–2.5×)
- Gradient explosion: SmoothL1 clips — safe
- Training noise: weighted loss reduces outlier sensitivity

## Acceptance Criteria
- [ ] `weighted_loss=True, eol_weight_scale=2.5` passed to `train_long()` and `train()` 
- [ ] Training logs show upweighted samples (weight > 1.0 in EOL region 75–85% SOH)
- [ ] Both `train()` and `train_long()` retrained → new artifacts saved to `models/weights/`
- [ ] Test metrics: MAE ≤ 1.80%, RMSE ≤ 2.8%, fewer > 3% errors in critical range
- [ ] EOL weight formula documented in CLAUDE.md (cite IEC 62619 + BatteryML arXiv 2310.14714)

## Steps
- [ ] Read `scripts/train.py` line 269, 340, 420 → understand current loss selection
- [ ] Verify `_soh_weighted_smooth_l1` implementation in model file (line 324)
- [ ] Add `weighted_loss=True, eol_weight_scale=2.5` as function parameters
- [ ] Implement EOL weight computation (samples near 80% SOH get 2–2.5× upweight)
- [ ] Update loss selection logic: if weighted_loss=True → use weighted SmoothL1 instead of MSELoss
- [ ] Run `python scripts/train.py --weighted-loss --eol-weight-scale 2.5 --data-dir data/processed --epochs 100`
- [ ] Verify training logs: check sample weights in debug output
- [ ] Check test metrics: MAE, RMSE, per-SOH error distribution
- [ ] Commit retrained artifacts: `soh_lstm_v1.x.pth`, `scaler.pkl`, `isolation_forest_v1.x.pkl`
- [ ] Update `CLAUDE.md` rules/tech/ai.md: document EOL weight formula + safety rationale

## Câu hỏi đã giải đáp
Không có — issue mô tả đầy đủ, code đã implement, chỉ cần enable + retrain.

## References
- Code: `scripts/train.py` line 324 (`_soh_weighted_smooth_l1`)
- Safety standard: IEC 62619 (critical SOH regions)
- BatteryML evidence: Kurtosis peaks near EOL (arXiv 2310.14714)
