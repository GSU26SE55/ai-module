# Plan — GH-10: Mở rộng MambaSOHPredictor chạy chuỗi dài L=4096

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-06-15
- **Issue:** #10 — https://github.com/GSU26SE55/ai-module/issues/10
- **Sprint:** Sprint 3 (due 2026-06-27)
- **Liên quan:** #9 (fix fp32 SSM scan) — branch hiện tại `fix/GH-9-mamba-fp32-scan`

## Mục tiêu
Mở rộng `MambaSOHPredictor` để dự đoán SOH mạnh ở chuỗi dài **L=4096** (hiện window=30, spec đã duyệt mở rộng — feature). Chuỗi 4096 được tạo bằng cách **ghép nhiều discharge cycle NASA liên tiếp của cùng 1 pin**; model xuất **1 SOH cho cả chuỗi** = SOH trạng thái hiện tại. Đạt **MAE < 2% / RMSE < 3%** và **inference < 100ms** (GPU bắt buộc; CPU benchmark + ghi nhận).

## Scope
**Trong scope (full-optimal P0–P4):**
- **P0 (điều chỉnh → P0-lite)** — ~~Viết lại `_selective_scan` theo chunkwise/SSD (matmul)~~ **KHÔNG khả thi**: A theo `(d_inner,d_state)` (Mamba-1) khiến ma trận decay SSD `(B,d_inner,d_state,C,C)` ≈ 172GB. Thay bằng: tối ưu chunked prefix-scan hiện có (slicing thay arange+gather, vẫn functional/autograd-safe) + gỡ dead `_parallel_scan`. Giữ kiến trúc + fp32 GH-9.
- **P1** — **Progressive sequence-length warmup** khi train: 256→512→1024→2048→4096, load weight nối tiếp giữa các mốc.
- **P2** — **Gradient accumulation** giữ effective batch=32 khi giảm micro-batch tránh OOM ở mốc 4096.
- **P3** — **Pooling** thay last-token: **causal-attention pooling** (mean-pool bị loại vì SOH biến thiên dọc chuỗi).
- **P4** — **Fast-path inference** riêng + benchmark <100ms trên **GPU và CPU**.
- Preprocess: pipeline mới tạo chuỗi L=4096 từ ghép cycle (sliding-window theo cycle để tăng số sample).

**Ngoài scope:**
- Không đổi kiến trúc baseline window=30 (giữ artifact `soh_mamba_v1.1.pth` cho inference 30 hiện tại — model dài lưu version riêng).
- Không thêm ML framework mới, không IoT pipeline (Sprint 8).
- Không đổi IsolationForest / anomaly mapping.

## Giả định cần duyệt (QUAN TRỌNG)
1. **Label chuỗi 4096 = SOH của cycle cuối cùng trong cửa sổ** (ước lượng trạng thái hiện tại từ lịch sử dài). Nếu hội đồng/GVHD muốn label khác (vd SOH trung bình) → dừng, đổi approach.
2. **Pooling = causal-attention** (không mean-pool) vì SOH thay đổi dọc chuỗi ghép.
3. **Rủi ro data-scarcity:** mỗi pin NASA ~160–170 cycle, ghép tới 4096 (~8–20 cycle/chuỗi) → chỉ còn **rất ít sample 4096** nếu non-overlap. Giảm thiểu bằng **sliding window theo cycle (stride < số cycle/chuỗi)**. Vẫn có nguy cơ overfit → theo dõi gap train/val; nếu MAE val không đạt, cân nhắc giảm L mục tiêu (2048).

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/core/config.py` | modify | Thêm `LONG_SEQ_LEN=4096`, `CYCLES_STRIDE`, `WARMUP_STAGES=[256,512,1024,2048,4096]`, `LONG_MODEL_PATH` (version riêng, vd `soh_mamba_long_v1.0.pth`); giữ `WINDOW_SIZE=30`. |
| `scripts/preprocess_long.py` | create | Pipeline mới: ghép cycle liên tiếp/pin → chuỗi 4096, label=SOH cycle cuối, FFT feature trên toàn cửa sổ, sliding theo cycle. Tái dùng scaler train hiện có. Output `data/processed_long/{train,val,test}.pt`. |
| `src/models/soh_predictor.py` | modify | P0: chunkwise/SSD scan; P3: thêm `pooling="attention"` (giữ `"last"` mặc định cho tương thích window=30); gỡ `_parallel_scan`. |
| `scripts/train.py` | modify | P1: vòng warmup theo `WARMUP_STAGES` (load weight nối tiếp); P2: `--accum-steps` gradient accumulation; tham số `--seq-len`, `--data-dir` cho data dài. Giữ fp32 recurrence + AMP + seed 42. |
| `src/services/inference.py` | modify | P4: fast-path L dài (eval, no checkpoint, CHUNK lớn, no grad); chọn device GPU nếu có. |
| `src/core/model_loader.py` | modify | Load long-model + metadata version; assert seq_len khớp. |
| `tests/test_models.py` | modify | Test chunkwise scan == sequential reference (sai số < 1e-4 fp32); shape ở L=4096; pooling output. |
| `tests/test_inference.py` | modify | Benchmark latency <100ms GPU; ghi nhận CPU; assert output ∈ [0,100]. |
| `tests/test_preprocess.py` | modify | Test chuỗi 4096 đúng length, label=cycle cuối, không leak cross-battery. |

## Approach
- **Data (preprocess_long):** với mỗi pin train (B0005/06/07), sort cycle theo `test_id`, ghép timestep liên tiếp tới khi đủ 4096 → 1 sample, label = SOH cycle cuối trong cửa sổ; trượt cửa sổ theo cycle (stride) để tăng sample. Val/test tách theo **battery ID** như spec (B0018), KHÔNG trộn cross-battery trong 1 chuỗi. Scaler MinMax tái dùng từ train (không refit).
- **P0 chunkwise/SSD scan:** chia L thành chunk (256); trong chunk tính state bằng `cumsum(log dA)` + masked matmul (tận dụng tensor core) thay prefix-scan element-wise + `torch.cat`; nối chunk qua carry state. Giữ fp32 trong recurrence. Verify bằng test so với scan tuần tự tham chiếu.
- **P1 warmup:** train tuần tự qua các mốc seq-len; sau mỗi mốc lưu `state_dict` → load vào mốc kế (param Mamba độc lập với L nên transfer hợp lệ). Mỗi mốc vài epoch; mốc 4096 chạy đủ epoch + early stopping.
- **P2 memory:** micro-batch nhỏ + `accum_steps` để effective batch=32; tune CHUNK (256→128) trước khi giảm batch.
- **P3 pooling:** causal-attention pool trên output Mamba (score qua linear → softmax theo thời gian → weighted sum) rồi mới FiLM + head. Mặc định giữ `"last"` để không phá inference window=30.
- **P4 inference:** fast-path tách riêng train path; benchmark GPU (mục tiêu <100ms) + CPU (ghi nhận, cảnh báo nếu vượt).

## Edge Cases
- Pin có tổng timestep < 4096 → bỏ qua hoặc pad có mask (quyết định: **bỏ qua**, log số sample bị loại).
- Chuỗi cuối của pin không đủ 4096 → drop phần dư (không pad).
- CPU inference vượt 100ms → KHÔNG fail test, ghi `warning` + log latency; SLA <100ms chỉ enforce trên GPU.
- AMP fp16 ở L=4096: recurrence vẫn fp32 (giữ logic #9), chỉ matmul lớn fp16.
- Seed 42 mọi script; cudnn.deterministic giữ nguyên.

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| Chunkwise scan đúng | `pytest tests/test_models.py` — output khớp scan tuần tự, sai số < 1e-4 |
| Train hội tụ ở L=4096 | Log train có đủ 5 mốc warmup, mốc 4096 chạy + early stop |
| MAE < 2% / RMSE < 3% | Test split (B0018) trong log train.py đạt target |
| Latency GPU < 100ms | `pytest tests/test_inference.py` assert pass trên GPU |
| Latency CPU ghi nhận | Benchmark CPU in ra log (không assert) |
| Coverage ≥ 85% | `pytest tests/ --cov=src` |
| Không vỡ inference window=30 | Test cũ vẫn pass (pooling mặc định `"last"`) |

## Steps
- [x] Bước 1 (Preprocess): viết `scripts/preprocess_long.py` ghép cycle → 4096 + test_preprocess — 2026-06-15
- [x] Bước 2 (Model P0-lite): tối ưu chunked prefix-scan (slicing) + gỡ dead `_parallel_scan` + test correctness (36/36, chunked==sequential L=600) — 2026-06-15
- [x] Bước 3 (Model P3): attention pooling option (mặc định `"last"` giữ window=30) + 4 test — 2026-06-15
- [x] Bước 4 (Train P1+P2): `train_long()` warmup stages + gradient accumulation + `--long` CLI + 3 test (smoke chạy end-to-end synthetic) — 2026-06-15
- [x] Bước 5 (Inference P4): `predict_soh_long` fast-path (no-ckpt khi no-grad, GPU nếu có) + `load_long_model` + 2 test — 2026-06-15
- [x] Bước 6 (Test + latency): unit test toàn bộ + benchmark L=4096 (GPU assert <100ms, CPU ghi nhận 169ms) — coverage 92% (≥85%) — 2026-06-15

## Câu hỏi đã giải đáp
- **Deploy:** cả GPU + CPU → fast-path riêng + benchmark 2 môi trường; SLA <100ms enforce GPU.
- **Spec:** đã duyệt mở rộng window — đây là feature (issue mới #10), không nhét vào fix #9.
- **Scope:** full-optimal (P0 SSD scan + P1 warmup + P2 grad-accum + P3 pooling + P4 benchmark).
- **Nguồn data L=4096:** ghép nhiều cycle NASA liên tiếp cùng pin.
- **Target:** 1 SOH cho cả chuỗi (seq→scalar) → label = SOH cycle cuối (giả định, cần duyệt).
- **Metric:** giữ MAE<2% / RMSE<3% + latency.
