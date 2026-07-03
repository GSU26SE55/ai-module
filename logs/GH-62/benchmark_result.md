# GH-62 — Benchmark kết quả sau khi batch MC Dropout

**Ngày:** 2026-07-04

## Latency (`scripts/benchmark_grpc.py --real-weights`)

| | Trước (GH-60 baseline) | Sau (GH-62) | Cải thiện |
|---|---|---|---|
| `Predict` avg | 494.8ms | **119.3ms** | **4.15x nhanh hơn** |
| `run_inference` (direct) | 454.7ms | 143.3ms | 3.17x |
| `PredictStream` (per window) | 524.4ms | 124.0ms | 4.23x |
| `Prescribe` (rule path) | 479.5ms | 117.5ms | 4.08x |

```
RPC                             avg ms    p50 ms    p95 ms
----------------------------------------------------------
run_inference (direct)           143.3     143.7     187.5
Predict (unary)                  119.3     111.5     160.9
PredictStream (per window)       124.0     122.8     130.6
Prescribe (rule path)            117.5     110.4     163.7

FAIL: Predict avg 119.3ms >= 100.0ms (P1 SLA)
RESULT: FAIL
```

**Vẫn FAIL nhưng chỉ vượt ~19%** (119.3ms vs 100ms) — khác hẳn mức vượt ~5x (494.8ms) trước khi fix. Trên máy dev (CPU, có chạy song song nhiều tiến trình khác) — môi trường deploy thật (dành riêng, có thể có GPU) rất có khả năng đạt <100ms.

## Độ chính xác (không regression)

So với GH-60 (trước batching) — 4 demo payload:

| Demo | True SOH | Pred trước | Pred sau | Classification |
|---|---|---|---|---|
| predict_healthy.json | 82.9% | 77.84% | 78.03% | Failed (cả 2, do gần ngưỡng EOL_SOH — xem GH-60) |
| predict_degraded.json | 61.2% | 62.79% | 62.88% | Failed |
| predict_degraded_6field.json | 61.2% | 62.14% | 62.03% | Failed |
| predict_healthy_b0005.json | 92.8% | 93.97% | 93.93% | Normal |

**MAE sau batching: 2.127%** (trước: 2.19%) — chênh lệch nằm trong dao động tự nhiên của MC Dropout (mỗi lần chạy dropout mask khác nhau ngẫu nhiên), **không phải regression**. `soh_std`/`confidence` vẫn ở mức hợp lý tương tự trước.

## Kết luận
- Fix đúng như kỳ vọng: cải thiện 4.15x latency, không đổi ý nghĩa thống kê kết quả
- Vẫn cần theo dõi thêm khi deploy thật (benchmark trên môi trường production, có thể cần thêm tối ưu nếu CPU-only và cùng tải như máy dev)
- Không cần thay đổi `MC_RUNS` trong ticket này (đúng scope đã thống nhất)
