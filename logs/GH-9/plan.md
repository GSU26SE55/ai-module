# Plan — GH-9: Fix Mamba SOH precision (fp32 SSM scan) + GPU reproducibility

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-06-15
- **Issue:** #9 — https://github.com/GSU26SE55/ai-module/issues/9
- **Sprint:** Sprint 3 (due 2026-06-27)

## Mục tiêu
MAE của Mamba SOH trên GPU (Kaggle) bị đội lên ≥2% — **vượt ngưỡng target <2%** —
trong khi local vẫn đạt <1%. Mục tiêu: kéo MAE trên GPU xuống dưới 2% (lý tưởng ~0.6%
như local). Nguyên nhân: phần
hồi quy SSM (selective scan) tích lũy state trong **fp16** dưới AMP, gây dồn sai số —
càng dài (hướng tới L=4096) càng tệ. Sửa để scan chạy **fp32** (đúng chuẩn Mamba gốc
`selective_scan_ref`: `u.float()`, `delta.float()`), giữ projection fp16 để vẫn vừa
bộ nhớ; đồng thời khóa reproducibility GPU để các lần train ra kết quả lặp lại được.

## Scope
**Trong scope:**
- Ép fp32 bên trong `_selective_scan` (cả 2 nhánh: sequential L≤512 và chunked L>512)
  và `_scan_forward_chunk` — bằng `torch.autocast(enabled=False)` + `.float()`,
  trả output về dtype gốc ở cuối (cast-back).
- Khóa reproducibility GPU trong `scripts/train.py`: `torch.cuda.manual_seed_all(42)`,
  `cudnn.deterministic=True`, `cudnn.benchmark=False`, và seed DataLoader (generator).
- Unit test: forward output ổn định + 2 lần init cùng seed ra weight giống nhau.

**Ngoài scope:**
- KHÔNG đổi kiến trúc (giữ FiLM + 54 spectral features, d_model=64, 2 MambaBlock).
- KHÔNG đổi data split / window=30 / hyperparameter (lr, batch, epochs).
- KHÔNG chuyển sang log-space scan hay Mamba-2 (để dành nếu fp32 vẫn chưa đủ).
- KHÔNG làm sequence-length warmup cho L=4096 (tách issue riêng nếu cần).

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/models/soh_predictor.py` | modify | `_selective_scan` + `_scan_forward_chunk` chạy fp32, cast-back dtype gốc |
| `scripts/train.py` | modify | thêm cuda seed + cudnn deterministic + DataLoader generator; log Device/AMP |
| `tests/test_soh_predictor.py` | create/modify | test precision-stability + reproducibility forward |

## Approach
- **Precision (soh_predictor.py):** đầu `_selective_scan` lưu `orig_dtype = x.dtype`,
  bọc toàn bộ thân hàm trong `with torch.autocast(device_type="cuda", enabled=False):`
  (no-op trên CPU), ép `x = x.float()` → các phép `x_proj`, `dt_proj`, `softplus`,
  `exp`, recurrence đều fp32; `h`/`h_carry` khởi tạo `dtype=torch.float32`. Cuối hàm
  `return (y + x*self.D).to(orig_dtype)` để `y*silu(z)` + `out_proj` tiếp tục fp16.
  → projection lớn (`in_proj`/`out_proj` trong `forward`) vẫn fp16 ⇒ vẫn tiết kiệm
  bộ nhớ cho L=4096, đúng mô hình "fp16 matmul + fp32 accumulation" của Mamba.
- **Reproducibility (train.py):** thêm `torch.cuda.manual_seed_all(SEED)` cạnh các seed
  hiện có; set `cudnn.deterministic=True` + `cudnn.benchmark=False` (thay dòng 125);
  truyền `generator=torch.Generator().manual_seed(SEED)` + `worker_init_fn` vào
  train DataLoader để khóa thứ tự shuffle.
- **Không đổi** train/val/test, loss, optimizer, scheduler, early-stopping.

## Edge Cases
- **CPU (không CUDA):** `autocast(device_type="cuda", enabled=False)` an toàn (no-op);
  `cuda.manual_seed_all` gọi được kể cả khi không có GPU (no-op). Không crash.
- **AMP đang bật (Kaggle GPU):** scan vẫn fp32 nhờ disable autocast cục bộ; phần ngoài
  scan giữ fp16 — không phá luồng GradScaler hiện tại.
- **L>512 (chunked + checkpoint):** `_ckpt(use_reentrant=False)` tương thích với input
  fp32; nếu fp32 gây OOM ở 4096 → giảm `CHUNK` 256→128 (ghi chú trong code, không làm sẵn).

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| Forward không đổi shape/giá trị hợp lệ | `pytest tests/test_soh_predictor.py -v` PASS |
| Output ổn định khi bật/tắt autocast | test so sánh fp32-path vs autocast-path sai lệch nhỏ |
| Train GPU lặp lại được | 2 lần train cùng seed → test MAE chênh < 0.05% (manual/Kaggle) |
| MAE < 2%, RMSE < 3% trên test | log cuối `scripts/train.py` báo ACHIEVED |
| Latency inference < 100ms | `pytest tests/test_inference.py` benchmark PASS |
| Coverage ≥ 85% | `pytest tests/ --cov=src` |

## Steps
- [x] Bước 1: Sửa `_selective_scan` + `_scan_forward_chunk` → fp32 + cast-back (`soh_predictor.py`) — 2026-06-15
- [x] Bước 2: Thêm cuda seed + cudnn deterministic + DataLoader generator/worker seed (`train.py`) — 2026-06-15
- [x] Bước 3: Log `Device`/`AMP` đầu train — đã có sẵn trong code, không cần thêm — 2026-06-15
- [x] Bước 4: Cập nhật test scan (API mới) + thêm test precision-stability + reproducibility — 2026-06-15
- [x] Bước 5: `pytest tests/ --cov=src` → test_models 36/36 PASS, coverage 90%, latency PASS — 2026-06-15
- [x] Bước 6: CPU smoke train (fp32 scan + seeded loader) OK; GPU Kaggle để chốt số MAE<2% — 2026-06-15

## Ghi chú thực thi
- **Deviation (đã được duyệt):** test `test_streaming_scan_matches_full_sequential_scan` đã hỏng sẵn
  từ trước (dùng API cũ `_selective_scan(x, chunk_size=)` + `_sequential_scan`) → sửa về API hiện tại,
  so sánh chunked vs sequential ở fp32.
- **2 test fail nằm ngoài scope GH-9** (`test_extractor::test_spectral_features_ignore_dc_offset`,
  `test_preprocess::test_load_split_rejects_stale_feature_version`) — đã verify hỏng sẵn từ baseline
  (fail cả khi stash thay đổi của GH-9). Cần tách issue riêng, KHÔNG fix trong GH-9.
- Reproducibility fix (`cuda.manual_seed_all`, `cudnn.deterministic`) chỉ tác động GPU → xác nhận
  cuối cùng phải chạy trên Kaggle GPU.

## Câu hỏi đã giải đáp
- **Nguyên nhân gốc:** xác định qua đối chiếu code với Mamba gốc — state khởi tạo
  `dtype=x.dtype` (`soh_predictor.py:81`) và `dtype=dt.dtype` (`:94`) = fp16 dưới AMP.
- **Vì sao không tắt hẳn AMP:** sẽ OOM ở L=4096 trên P100; Mamba gốc cũng chỉ ép fp32
  cho riêng phần recurrence, giữ matmul fp16.
- **0.61% local vs ≥2% Kaggle:** chênh do AMP chỉ bật trên CUDA (`train.py:126`),
  local fp32 nên không lộ bug; fix này xóa khác biệt môi trường đó.
