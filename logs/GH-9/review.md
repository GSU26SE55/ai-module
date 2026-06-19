## BÁO CÁO CODE REVIEW — fix/GH-9-mamba-fp32-scan — 2026-06-15
### Scope: AI
### Effort: Deep (thay đổi precision lõi model + reproducibility)

### TÓM TẮT
Fix đúng nguyên nhân gốc: ép phần hồi quy SSM chạy fp32 (đúng chuẩn Mamba `selective_scan_ref`)
trong khi giữ projection fp16, cộng khóa reproducibility GPU. Code chính xác, có test bao phủ
cả 3 khía cạnh (chunked==sequential, cast-back dtype, shielding khỏi autocast). Không phát hiện
Critical. PASS.

### PHÂN TÍCH

✅ **Pass — Reproducibility**
- `SEED=42` + `torch.manual_seed` + `torch.cuda.manual_seed_all(SEED)` (train.py:40) ✓
- DataLoader `generator` + `worker_init_fn=_seed_worker` (train.py) → khóa thứ tự shuffle ✓
- `cudnn.deterministic=True` + `benchmark=False` (train.py) → không autotune đổi thuật toán giữa các run ✓

✅ **Pass — Precision (root-cause)**
- `_selective_scan`: `with torch.autocast(device_type=dev_type, enabled=False)` + `x.float()`;
  `h`/`h_carry`/`y` khởi tạo `torch.float32`; `return y.to(orig_dtype)` (soh_predictor.py:65-122)
  → đúng mô hình "fp16 matmul + fp32 accumulation" của Mamba gốc.
- `_scan_forward_chunk` nhận input fp32 từ caller → toàn bộ chunk fp32 (đã ghi chú docstring) ✓
- Cast-back giữ `in_proj`/`out_proj` fp16 → không phá mục tiêu bộ nhớ cho L=4096 ✓

✅ **Pass — Checkpoint/autocast interaction**
- `_ckpt(use_reentrant=False)` trong block disable-autocast, inputs fp32; recompute (backward) chạy
  ngoài autocast → vẫn fp32. Không lệch precision forward/backward.

✅ **Pass — Test coverage**
- `test_streaming_scan_matches_full_sequential_scan` sửa về API mới, so chunked vs fp32 sequential
- `test_selective_scan_preserves_input_dtype` — verify cast-back
- `test_selective_scan_runs_fp32_under_autocast` — verify shielding khỏi AMP (test gốc rễ)
- `test_model_forward_reproducible_same_seed` — reproducibility unit-level
- Kết quả: `pytest tests/test_models.py` → 36/36 PASS; coverage tổng 90% (`soh_predictor.py` 88%)

✅ **Pass — Không đụng data/scaler/model count**
- Không thay đổi data split, không fit lại scaler, không thêm model thứ 3. Đúng scope, surgical.

🟡 **Warning — soh_predictor.py: determinism không bit-exact tuyệt đối**
- `cudnn.deterministic=True` xử lý conv, nhưng chưa gọi `torch.use_deterministic_algorithms(True)`.
  Một vài CUDA op vẫn có thể dùng atomics non-deterministic. Đủ cho mục tiêu "MAE chênh <0.05%",
  nhưng không đảm bảo bit-exact. Gợi ý: cân nhắc bật ở issue riêng nếu cần reproducibility tuyệt đối
  (rủi ro: một số op thiếu kernel deterministic sẽ raise lỗi → phải test kỹ).

🟡 **Warning — requirements.txt chưa pin version (pre-existing, ngoài diff GH-9)**
- Checklist reproducibility yêu cầu pin lib version. Không thuộc thay đổi GH-9 nhưng ảnh hưởng tính
  lặp lại cross-môi trường (local vs Kaggle). Đề xuất xử lý ở chore riêng.

### RỦI RO & LƯU Ý
- **Số chốt cuối phải chạy Kaggle GPU:** fix reproducibility là no-op trên CPU; phải verify trên
  GPU rằng MAE về ~mức local (<1%) và 2 lần train ra giống nhau.
- **2 test fail ngoài scope** (`test_extractor::test_spectral_features_ignore_dc_offset`,
  `test_preprocess::test_load_split_rejects_stale_feature_version`) — đã verify hỏng sẵn từ baseline.
  KHÔNG fix trong GH-9; nên tạo issue riêng.
- **Base branch khi ship:** GH-9 branch off `feat/spectral_kurtosis` (code chunked-scan chỉ tồn tại ở
  đó). PR phải target đúng base này, không phải `dev`. Lưu ý cho `/kltn-ship`.
- **`docs/overall.md`** đang có thay đổi khổng lồ chưa commit, KHÔNG liên quan GH-9 → loại khỏi commit khi ship.

### KẾT LUẬN
**PASS** — Độ tự tin: **Cao**
(Code đúng nguyên nhân gốc đã research, khớp chuẩn Mamba chính thức, test bao phủ đủ, surgical đúng scope.
Verify cuối cùng trên Kaggle GPU là bước còn lại để chốt metric.)
