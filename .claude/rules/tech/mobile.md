# Tech — Mobile (React Native / Expo)

## Stack

| Quyết định | Lựa chọn | Ghi chú |
|------------|----------|---------|
| Framework | React Native (Expo) | Không cần native build phức tạp |
| Navigation | Expo Router | File-based routing |
| HTTP | Axios | Shared config pattern với Web |
| State | Zustand | Nhất quán với Web |

## Nguyên tắc

- Không thêm package mới nếu stack hiện tại đủ giải quyết — hỏi Leader trước
- Không eject khỏi Expo managed workflow trong scope capstone
- Axios config (base URL, interceptors) giữ nhất quán với Web
