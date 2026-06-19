# Plan — GH-12: Realtime variable-length SOH serving (sliding window-30)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-06-16
- **Issue:** #12 — https://github.com/GSU26SE55/ai-module/issues/12
- **Sprint:** Sprint 3 (due 2026-06-27)
- **Liên quan:** #10 (L=4096 negative result → chốt hướng serving thay vì train dài)

## Mục tiêu
Cho `/predict` nhận buffer độ dài linh hoạt (**≥30 token**) thay vì ép đúng 30, phục vụ realtime stream. SOH lấy từ **30 reading gần nhất** (đúng phân phối model `v1.1` đã học → MAE 0.61% cho MỌI độ dài input). Trend/RUL tận dụng **toàn bộ buffer dài**. **KHÔNG retrain.**

## Scope
**Trong scope:**
- Nới validation `PredictRequest`: `== 30` → `>= 30` (giữ kiểm tra feature-count 3/6).
- `run_inference`: trim buffer về **30 gần nhất** cho model + x_feat; giữ **full buffer** cho `compute_degradation_metrics` / `generate_warnings` / `feature_summary`.
- Test: variable-length (30/100/4096) ra cùng SOH như last-30; latency <100ms với buffer dài; reject <30.

**Ngoài scope:**
- KHÔNG retrain, KHÔNG đổi model/architecture, KHÔNG đụng pipeline L=4096 (GH-10).
- KHÔNG đổi response schema (`PredictResponse` giữ nguyên).
- Endpoint streaming trend (trượt window trả chuỗi SOH) — **để sau** (future), không làm lần này (Simplicity First).

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/schemas/predict.py` | modify | Validator `len < WINDOW_SIZE` → reject; cho phép `>= WINDOW_SIZE`; update docstring |
| `src/services/inference.py` | modify | `run_inference`: `x_window = x_scaled[-WINDOW_SIZE:]` cho model + x_feat; full `raw` cho degradation/warnings/summary |
| `tests/test_routers.py` | modify | Test request ≥30 pass (100, 4096), <30 reject |
| `tests/test_inference.py` | modify | Test buffer dài → SOH == last-30; latency <100ms; trend dùng full buffer |

## Approach
- **Phân tách đúng (key design):** SOH hiện tại ← **last-30** (model window=30, byte-giống hành vi hiện tại → 0.61%); trend/RUL/cảnh báo ← **full buffer** (lịch sử dài, `compute_degradation_metrics` đã hỗ trợ). → "mọi độ dài input cùng accuracy 0.61%" mà vẫn dùng được history dài cho trend.
- **Vì sao trim chứ không feed cả buffer vào model:** đã chứng minh window dài hơn → accuracy tệ hơn (#10: 0.61%→3.81%). Trim về 30 = đưa model đúng phân phối train → giữ 0.61%.
- **Latency:** model chỉ thấy 30 token → ~5ms bất kể buffer dài; degradation là numpy ops nhanh → tổng vẫn <100ms.
- **Backward-compat:** input đúng 30 → hành vi y hệt hiện tại (last-30 của 30 = chính nó).

## Edge Cases
- `len(readings) < 30` → ValidationError rõ ràng (giữ message dạng cũ).
- `len(readings) == 30` → giữ nguyên hành vi cũ (regression phải pass).
- Buffer rất dài (vd 4096) → trim last-30, không OOM, latency vẫn thấp.
- Feature-count vẫn validate 3 (legacy) / 6.

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| Nhận input ≥30 | `pytest test_routers` — 100 & 4096 token pass |
| Reject <30 | ValidationError |
| Mọi độ dài → cùng SOH | SOH(buffer) == SOH(buffer[-30:]) trong test |
| Latency <100ms với buffer dài | benchmark trong test_inference |
| Regression 30-input | test cũ pass nguyên |
| Coverage ≥85% | `pytest --cov=src` |

## Steps
- [x] B1 (Schema): nới `PredictRequest` validator ≥30 + test_routers (nhận 120 token) — 2026-06-16
- [x] B2 (Inference): `run_inference` — Mamba ← last-30; **x_feat ← FULL buffer** (cycle-level, FIX Critical phát hiện khi test data thật); trend ← full buffer + test `features_computed_on_full_buffer` — 2026-06-16
- [x] B3 (Latency): test buffer 4096 → SOH hợp lệ + latency không phình theo độ dài — 2026-06-16
- [x] B4 (Test): full suite 91 passed / 2 pre-existing / coverage 92% — 2026-06-16

## Câu hỏi đã giải đáp
- **Có cần train lại không?** KHÔNG — reuse `v1.1` (0.61%); fix ở tầng serving.
- **Mọi độ dài cùng accuracy?** Có — trim về last-30 → đúng phân phối train → 0.61% cho mọi input length.
- **Token dài có phí không?** Không — dùng cho trend/RUL (degradation metrics), SOH dùng last-30.
- **Streaming trend endpoint?** Để sau, không trong scope lần này.
