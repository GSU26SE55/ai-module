# Plan — LowSoc / điện áp thấp: chuyển sang notification-only (phần AI)

## Metadata
- **Status:** IMPLEMENTED (phần AI) | **Role:** AI | **Ngày:** 2026-09-01
- **Issue:** _chưa có — cần tạo, plan này viết trước theo yêu cầu trực tiếp của user_
- **Branch:** `fix/lowsoc-notification-only`
- **Phần BE:** chưa làm, xem §"Bàn giao BE" cuối file

## Mục tiêu
Pin được dùng đến hết là **trạng thái vận hành**, không phải sự cố. Hiện hệ thống sinh
ticket cho tình huống này qua hai cửa khác nhau:

1. `LowSoc` (BE) — SOC dưới ngưỡng → Alert → auto-create ticket
2. `VOLTAGE_LOW` (AI) — điện áp sát cutoff → `severity="warning"` → risk Medium/P3 →
   `SCHEDULE_MAINTENANCE` → ticket

Cửa (2) là hình bóng vật lý của cửa (1): LFP 8S xả cạn tụt xuống ~22.4 V, dưới ngưỡng
`VOLTAGE_LOW` 2.8 V/cell. Đóng một cửa mà không đóng cửa kia thì ticket rác vẫn ra, chỉ
đổi nhãn.

Ngoài ra `verify.py` đang **cộng điểm hợp lệ** cho ticket khi SOC dưới ngưỡng — tức AI
xác nhận cho Manager một sự cố không tồn tại.

## Scope
**Trong scope (AI module):** `verify.py`, `anomaly_detector.py`, knowledge base, docs BE.
**Ngoài scope:** BE (`ThresholdAnomalyDetector`, `BatteryAnomalyDetectedConsumer`) — làm sau.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/verify.py` | modify | Bỏ SOC khỏi bằng chứng lỗi; trả thêm `soc_low` để câu lý do nói đúng sự thật |
| `src/models/anomaly_detector.py` | modify | `VOLTAGE_LOW` severity `warning` → `info` |
| `tests/test_verify.py` | modify | 2 test mới khoá hành vi SOC |
| `tests/test_models.py` | modify | 2 test mới khoá severity `VOLTAGE_LOW`/`VOLTAGE_CRITICAL` |
| `knowledge/maintenance/bms_warning_codes.md` | modify | Bảng severity → P-priority |
| `knowledge/maintenance/anomaly_soc_soh.md` | modify | Mục `LowSoc` → notification-only |
| `knowledge/maintenance/solar_operations.md` | modify | Câu về `LowSoc` cho khớp |
| `models/embeddings/*` | regenerate | `python scripts/ingest_rag.py` (bắt buộc, nếu không `test_kb_manifest` đỏ) |
| `docs/grpc-integration-be.md` | modify | §7.3 cụm sensor + ghi chú SOC |
| `docs/be-huong-dan-tich-hop.md` | modify | §10.3 mới — thay đổi hành vi `VOLTAGE_LOW` |
| `docs/examples/grpc-payloads.json` | modify | 4 chỗ severity `VOLTAGE_LOW` |

## Quyết định thiết kế
- **Giữ `soc_warning_threshold` (proto field 9)** — wire compatibility, BE không phải đổi gì.
- **`VOLTAGE_CRITICAL` giữ `critical`** — dưới cutoff BMS là nguy cơ hư cell thật.
- **Cùng mức phạt −0.20 cho cả hai nhánh "không có bằng chứng"**, chỉ khác câu chữ: SOC thấp
  không cộng cũng không trừ. Nói *"stayed within every threshold"* khi SOC đang dưới ngưỡng
  là sai sự thật với chính dữ liệu Manager đang nhìn.
- **Tiền lệ bám theo:** `INSUFFICIENT_DISCHARGE` đã dùng đúng cơ chế `severity="info"` để
  không leo thang risk (`tests/test_models.py`, `docs/be-huong-dan-tich-hop.md` §10.2).

## Steps
- [x] Tạo branch `fix/lowsoc-notification-only`
- [x] `verify.py` — SOC thôi là bằng chứng lỗi + câu lý do trung thực
- [x] `anomaly_detector.py` — `VOLTAGE_LOW` → `info`
- [x] Tests (4 test mới)
- [x] Knowledge base + re-ingest manifest
- [x] Docs BE
- [x] `pytest` + `ruff check` PASS
- [ ] `/kltn-reviewcode`
- [ ] Bàn giao commit message cho user (KHÔNG tự commit/push)

## Bàn giao BE (chưa làm)
| # | Nơi | Việc |
|---|-----|------|
| B1 | `BatteryAnomalyDetectedConsumer.Consume()` | `LowSoc` vào set notification-only, return trước dedup BR-02. Sửa ở consumer chứ KHÔNG ở detector — event vẫn phải publish để NotificationService gửi noti |
| B2 | `ThresholdAnomalyDetector` | Hạ severity: `SocWarning` → Info, `SocCritical` → Warning. Giữ Critical là khách nhận "🔴 Cảnh báo nghiêm trọng" mỗi tối |
| B3 | BR-03 dedup | LowSoc dedup theo cửa sổ đủ dài (ngày, không phải phút) |
| B4 | *(tuỳ chọn)* | Ngưỡng deep-discharge riêng, thấp hơn `SocCritical`, hoặc dùng `VoltageMin` sẵn có → vẫn tạo ticket cho ca hư hại thật |
