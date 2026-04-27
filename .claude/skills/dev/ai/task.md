# Skill: /kltn-task (AI)

## Kích hoạt
`/kltn-task KAN-XX` — làm việc trên Jira ticket phía AI/ML module.

---

## Quy trình

1. **Đọc ticket** — fetch từ Jira, xác định: training / evaluation / API endpoint / data processing?
2. **Viết plan.md** tại `logs/KAN-XX/plan.md` với nội dung:
   ```markdown
   # Plan — KAN-XX: [Tên ticket]

   ## Mục tiêu
   [Training / evaluation / API endpoint / data processing?]

   ## Các file sẽ tạo/sửa
   | File | Hành động | Mô tả |
   |------|-----------|-------|
   | models/xxx.py | create/modify | ... |

   ## Approach
   [Thuật toán, data flow, model architecture]

   ## Dependencies & Edge Cases
   - random_seed, data leakage risk?
   - Dataset: NASA / CALCE / MIT?

   ## Ước tính
   - Size: Small / Medium / Large
   - Thời gian: X giờ
   ```
   > **DỪNG LẠI — chờ user xác nhận ("ok", "approve", "tiến hành") trước khi code.**
   > **TUYỆT ĐỐI KHÔNG CODE khi chưa có xác nhận. Không có ngoại lệ, dù ticket nhỏ đến đâu.**

3. **Tạo branch** — `feature/KAN-XX-ten-tinh-nang`
4. **Implement** theo đúng cấu trúc:
   - `data/` — script xử lý dataset (NASA/CALCE/MIT)
   - `models/` — định nghĩa model (PyTorch)
   - `train/` — training script
   - `api/` — FastAPI endpoint phục vụ BE gọi
4. **Tự kiểm tra** trước commit (xem `/code-review`)
5. **Commit** — `feat(KAN-XX): mô tả ngắn`
6. **Cập nhật Jira** — chuyển sang IN PROGRESS

## Không được
- Train model mà không set `random_seed` (kết quả không reproducible)
- Dùng test data trong quá trình training (data leakage)
- Overpromise accuracy — target thực tế capstone: **85–90%**, không phải 99%+
- Thêm model thứ 3+ mà chưa có approval (focus: LSTM/CNN-LSTM + 1 anomaly model)

## Stack AI
Python 3.11 · PyTorch · scikit-learn · FastAPI · NASA Ames Dataset (ưu tiên)
