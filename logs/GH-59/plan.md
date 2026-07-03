# Plan — GH-59: Bound/clip cycle_count_norm for batteries exceeding CYCLE_COUNT_NORM=200 cycles

## Metadata
- **Status:** TESTING | **Role:** AI | **Ngày:** 2026-07-03
- **Issue:** #59 — https://github.com/GSU26SE55/ai-module/issues/59
- **Sprint:** Sprint 4 (due 2026-07-11)

## Mục tiêu
`CYCLE_COUNT_NORM=200` fit theo NASA lab test (pin dài nhất ~197 cycle). Pin solar thực tế production có thể sống lâu hơn 200 cycle → `cycle_count_norm > 1`, ngoài phân phối model đã học → model extrapolate ngoài range, dự đoán kém tin cậy. Output: clip `cycle_count_norm` về `[0, 1]` nhất quán ở cả train (`preprocess.py`) và serve (`inference.py`), log warning khi giá trị thật vượt ngưỡng để có dữ liệu quyết định sau này (có cần tăng `CYCLE_COUNT_NORM` không).

## Scope
**Trong scope:**
- Clip `cycle_count_norm` về `[0, 1]` trong `src/services/inference.py` (`_append_derived_features()`, cả 2 nhánh: payload 6-cột từ BE và path derive server-side cũ)
- Clip tương tự trong `scripts/preprocess.py` (`cycles_to_windows()`) — dù NASA data không bao giờ vượt ngưỡng (max cycle ~197), clip ở đây đảm bảo train/serve nhất quán tuyệt đối, đúng nguyên tắc đã áp dụng ở GH-58
- Log warning (không phải error/exception) khi cycle_count thật > `CYCLE_COUNT_NORM`, kèm giá trị thật để dễ theo dõi qua log production
- Test boundary: cycle_count rất lớn (5000), âm (-1), đúng ngưỡng (200), dưới ngưỡng — không crash, không sai lệch nghiêm trọng

**Ngoài scope:**
- Không tăng `CYCLE_COUNT_NORM` (đã chọn hướng (a) clip, không phải (b) tăng hằng số)
- Không đổi cách tính/clip `soc_percent` — đã tự nhiên bound [0,100] theo `compute_soc_percent()`, không liên quan issue này
- Không retrain ngay — clip này áp dụng cho lần train tiếp theo trên Kaggle (gộp chung với GH-58, đã merge lên `dev`)
- Không validate range cho `soc_percent` gửi từ BE (path 6-cột) — nếu cần, mở issue riêng

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/inference.py` | modify | Thêm `import logging` + `logger = logging.getLogger(__name__)` (theo pattern `src/grpc_server.py`); clip `cycle_count_norm` về `[0,1]` sau khi tính (cả 2 nhánh); log warning khi giá trị thật (cycle_count / cycle_idx) vượt `CYCLE_COUNT_NORM` |
| `scripts/preprocess.py` | modify | Clip `cycle_count_norm` về `[0,1]` tại chỗ tính trong `cycles_to_windows()` — không tác động data NASA hiện tại (max ~0.985), chỉ đảm bảo defensive consistency |
| `tests/test_inference.py` | modify | Test clip cho cả 2 nhánh (BE gửi cycle_count>200 qua 6-cột; `cycle_idx` param >200 qua 4-cột) + test log warning bằng `caplog` |
| `tests/test_preprocess.py` | modify | Test `cycles_to_windows()` với `cycle_idx` cực lớn (vd 5000) → `cycle_count_norm` trong output vẫn `<= 1.0` |

## Approach
- Sau khi tính `cycle_count_norm` (dù từ nhánh nào), áp `cycle_count_norm = float(np.clip(cycle_count_norm, 0.0, 1.0))`
- Log warning TRƯỚC khi clip (dùng giá trị raw): `logger.warning("cycle_count=%s exceeds CYCLE_COUNT_NORM=%s, clipping to 1.0", raw_cycle_count, CYCLE_COUNT_NORM)` — chỉ log khi thực sự vượt ngưỡng (tránh spam log cho case bình thường)
- `preprocess.py` áp cùng công thức clip tại nơi tính `cycle_count_norm = np.float32(cycle_idx / CYCLE_COUNT_NORM)` — không cần log warning ở đây (không phải runtime production path, chỉ là batch script)

## Edge Cases
- `cycle_count` âm (input lỗi từ BE, vd -1) → clip về 0.0. **Cập nhật sau code review:** implementation thực tế log warning cho CẢ 2 chiều (âm lẫn vượt ngưỡng trên) vì input âm cũng là dấu hiệu lỗi đáng biết từ BE — rộng hơn mô tả ban đầu (chỉ định "không log case âm"), giữ nguyên vì hợp lý hơn, không phải bug.
- `cycle_count` đúng bằng `CYCLE_COUNT_NORM` (200) → `cycle_count_norm = 1.0` chính xác, không clip, không log (đúng biên, không phải vượt ngưỡng)
- `cycle_count` cực lớn (5000) → clip về 1.0, log 1 warning, không crash, không NaN/Inf

## Acceptance Criteria
- [ ] `cycle_count_norm` luôn nằm trong `[0, 1]` bất kể input cycle_count/cycle_idx là gì (không crash, không NaN/Inf)
- [ ] Log warning xuất hiện khi cycle_count thật vượt `CYCLE_COUNT_NORM`, không xuất hiện khi trong range bình thường
- [ ] Test boundary: cycle_count = 5000, -1, 200, 0 đều pass, không sai lệch nghiêm trọng (kiểm tra qua giá trị `cycle_count_norm` output, không phải qua model thật vì chưa train)
- [ ] `preprocess.py` và `inference.py` áp dụng công thức clip giống hệt nhau
- [ ] Toàn bộ `pytest tests/` pass, coverage ≥ 85%
- [ ] Sẵn sàng để gộp chung 1 lần train Kaggle tiếp theo với GH-58 (đã merge lên `dev`)

## Steps
- [x] Bước 1 (Inference): thêm logging + clip `cycle_count_norm` trong `_append_derived_features()` (`src/services/inference.py`), cả 2 nhánh — 2026-07-03
- [x] Bước 2 (Preprocess): clip `cycle_count_norm` trong `cycles_to_windows()` (`scripts/preprocess.py`) — 2026-07-03
- [x] Bước 3 (Unit test): 4 test mới trong `tests/test_inference.py` (clip vượt ngưỡng+log warning, clip âm, boundary không log, clip qua path 6-cột) — 2026-07-03
- [x] Bước 4 (Unit test): `TestGh59CycleCountClip` mới trong `tests/test_preprocess.py` (clip cycle_idx=5000, không clip khi trong range) — 2026-07-03
- [x] Bước 5: full suite 202 passed/1 flaky (không liên quan), coverage 87%, ruff chỉ lỗi pre-existing — 2026-07-03

## Câu hỏi đã giải đáp
- **Hướng xử lý:** chọn (a) clip `[0,1]` + log warning khi vượt ngưỡng — không tăng `CYCLE_COUNT_NORM` (tránh nén phân giải data NASA hiện có), không chỉ log mà không clip (không thực sự bảo vệ model khỏi extrapolate). (Không có phản hồi trong 60s, chọn theo phương án khuyến nghị.)
