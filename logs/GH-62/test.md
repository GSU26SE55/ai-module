## TEST REPORT — GH-62 — 2026-07-04
### Scope: AI
### Môi trường: local

### TÓM TẮT
Batch MC Dropout hoạt động đúng, cải thiện latency 4x, không regression độ chính xác/reproducibility. Vẫn FAIL SLA <100ms tuyệt đối trên máy dev (CPU chia sẻ tải), nhưng mức vượt giảm mạnh từ ~5x xuống ~1.2x.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Full `tests/test_inference.py` | — | pass | 25/25 pass | ✅ PASS |
| `test_mc_dropout_batched_still_stochastic` | `run_inference(dummy)` | `soh_std > 0` (dropout không bị collapse) | pass | ✅ PASS |
| `test_mc_dropout_batched_faster_than_naive_loop` | so sánh batched vs sequential cùng model | batched nhanh hơn | pass (chạy lại 5 lần liên tiếp, cả 5 đều pass — không flaky) | ✅ PASS |
| Full suite `pytest tests/ --cov=src` | — | ≥85% coverage, pass | 205 passed / 0 failed, 87% | ✅ PASS |
| Latency benchmark thật (`--real-weights`) | `Predict` RPC | cải thiện rõ rệt so baseline 494.8ms | 124.1ms (chạy lại lần nữa để xác nhận, trước đó 119.3ms — dao động nhỏ, đều quanh mức cải thiện ~4x) | ✅ PASS (cải thiện đạt kỳ vọng, dù chưa <100ms tuyệt đối) |
| Demo payload accuracy (4 mẫu) | so với GH-60 baseline | không regression | MAE 2.127% (GH-60: 2.19%) — trong dao động MC Dropout | ✅ PASS |

### Coverage
- Line coverage: **87%** (target ≥ 85%) — `src/services/inference.py` 95%

### Bugs tìm được
- Không có bug.

### RỦI RO & LƯU Ý
- **Latency tuyệt đối vẫn FAIL** trên máy dev (124.1ms > 100ms SLA) — đã cải thiện 4x nhưng chưa đạt ngưỡng cứng. Cần benchmark trên môi trường deploy thật (có thể GPU hoặc CPU dedicated không chia tải) trước khi kết luận cuối cùng có cần tối ưu thêm hay không — quyết định này ngoài scope GH-62 (đã ghi rõ từ đầu).
- Warning đã nêu ở code review (`test_mc_dropout_batched_faster_than_naive_loop` là timing-based test) — đã chạy lại 5 lần liên tiếp trong bước test này, không flaky trên máy hiện tại.

### KẾT LUẬN
PASS — Độ tự tin: Cao
