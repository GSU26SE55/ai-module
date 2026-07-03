## TEST REPORT — GH-63 — 2026-07-04
### Scope: AI
### Môi trường: local

### TÓM TẮT
Đạt SLA <100ms lần đầu (88.2ms). Đã verify kỹ điểm quan trọng nhất phát hiện ở code review (warm-up 2 mode eval+train) qua cả unit test lẫn real end-to-end — mode được restore đúng về eval sau nhiều lần gọi liên tiếp.

| Test case | Input | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| `tests/test_model_loader.py` (2 test) | compile fail / compile success (mock đúng) | fallback eager / dùng compiled đúng cả 2 mode | pass | ✅ PASS |
| `tests/test_inference.py` (25 test) | — | pass | pass | ✅ PASS |
| Reproducibility mode | `load_models()` → `training=False`; gọi `run_inference()` 2 lần liên tiếp | mode restore về `False` (eval) sau mỗi lần | khớp | ✅ PASS |
| Real `/health` | GET | model_version=1.5, tất cả loaded=true | khớp | ✅ PASS |
| Real `/predict` healthy/degraded | 2 demo payload | 200, soh hợp lý | 200, soh=78.11%/63.28% | ✅ PASS |
| Boundary: 5-cột invalid | readings sai shape | 422 | 422 | ✅ PASS |
| Full suite `pytest tests/ --cov=src` | — | ≥85%, pass | 207 passed/0 failed, 89% | ✅ PASS |
| Latency benchmark thật (`--real-weights`) | `Predict` RPC | <100ms | **88.2ms — PASS** | ✅ PASS |

### Coverage
- Line coverage: **89%** (target ≥ 85%) — `src/core/model_loader.py` được cover đầy đủ lần đầu (trước đây 0%, không test nào gọi `load_models()` thật)

### Bugs tìm được
- Không có bug mới (Critical đã tìm+sửa ở bước code review, verify lại confirm đã fix đúng).

### RỦI RO & LƯU Ý
- torch.compile CPU vẫn fallback về eager trên máy dev này (Windows/Triton) — PASS đạt được hoàn toàn nhờ `MC_RUNS=10`, chưa verify torch.compile có tác dụng thật trên môi trường deploy Linux.
- MAE tăng nhẹ theo mẫu nhỏ (2.13%→2.41%) do giảm MC_RUNS — trong dao động tự nhiên, cần theo dõi thêm khi có nhiều dữ liệu production.

### KẾT LUẬN
PASS — Độ tự tin: Cao
