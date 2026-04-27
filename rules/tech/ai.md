# Tech — AI Module

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Language | Python 3.11 | — |
| ML Framework | PyTorch | LSTM/CNN-LSTM |
| Anomaly | scikit-learn Isolation Forest | Đủ cho scope capstone |
| Serving | FastAPI | REST endpoint cho BE gọi |
| Dataset | NASA Ames (ưu tiên) | CALCE backup |

## Nguyên tắc

- Không thêm ML framework mới — chỉ PyTorch + scikit-learn
- Target accuracy thực tế: 85–90%, không overpromise 99%+
- Output bắt buộc: Classification (Normal / Degrading / Failed) + SOH % + confidence score
- IoT data pipeline chỉ thêm Sprint 8 nếu core model xong
