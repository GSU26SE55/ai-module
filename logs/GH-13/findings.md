# Findings — GH-13: Long-context SOH (cycle-axis, RUL, forecasting)

## Metadata
- **Ngày:** 2026-06-17 | **Role:** AI | **Branch:** `feat/GH-13-rul-cycle-level`
- **Issue:** #13 — https://github.com/GSU26SE55/ai-module/issues/13
- **Bối cảnh:** điều tra vì sao mở rộng MambaSOHPredictor sang chuỗi dài (L=4096, GH-10)
  cho kết quả kém (MAE 3.81%), và liệu các reframing long-context có cải thiện được không.

---

## TL;DR
Đã thực nghiệm cạn kiệt mọi hướng long-context / thêm-data. **Kết luận có bằng chứng cứng:**
- **Nowcasting (window=30) MAE 0.61% là kết quả mạnh thật** — dựa vào quan hệ vật lý
  gần-tất-định giữa hình dạng cycle và SOH hiện tại → transfer tốt cross-battery.
- **Mọi hướng dự đoán tương lai (RUL, forecasting) đều thất bại hoặc bị baseline tầm
  thường đè bẹp.** Đặc biệt: forecasting SOH +10 cycle bị **persistence (đoán không đổi)
  = 2.35% MAE** thắng mọi model deep learning.
- **Thêm pin KHÔNG giúp** — làm tệ hơn do domain/magnitude shift giữa các nhóm pin NASA.

→ Đóng góp đề tài: nowcasting 0.61% (cycle-axis + physics features) + phân tích trung
thực vì sao long-context không pay off trên NASA.

---

## 1. Phát hiện nền tảng về dữ liệu

| | Giá trị |
|---|---|
| Pin trong metadata / có file trên đĩa | 34 / 34 (7,565 CSV) |
| Pin dùng theo SPEC (khóa cứng) | **4** — train B0005/06/07, val/test B0018 |
| Cycle/pin | 25 → 197 (4 pin gốc: 132–168) |
| Cycle length (median) | ~314 timestep |
| 1 window L=4096 raw | trùm **~13 chu kỳ** → pha loãng tín hiệu + FFT méo ở điểm nối |

**Insight:** trục "dài" có ý nghĩa của NASA là **trục CHU KỲ (~168)**, không phải timestep.
L=4096-raw-timestep sai trục → đó là lý do GH-10 ra 3.81%.

---

## 2. Các thí nghiệm & kết quả

Tất cả test trên B0018 (held-out), eval trung thực:

| Hướng | Setup | Kết quả | Kết luận |
|---|---|---|---|
| Nowcasting | window=30, 4 pin | **MAE 0.61%** ✅ | mạnh thật (vật lý) |
| L=4096 raw | timestep axis | MAE 3.81% ❌ | sai trục, feature loãng |
| RUL cycle-level | lookback 30, LOBO | MAE 14.1 ± 5.1 cycles ❌ | extrapolation khó, 3 pin quá ít |
| Forecast +10 (absolute) | 4 pin, LOBO | MAE 8.93% (B0018 11.15%) ❌ | thua naive-mean 6.39% |
| Forecast +10 (absolute) | **25 pin** | MAE **42.61%** ❌ | domain shift (SOH 0–122% vs 67–86%) |
| Forecast +10 (DELTA) | 25 pin, anchor | MAE **40.66%** ❌ | magnitude shift (pin xả sâu) |
| **Persistence** (đoán không đổi) | — | **MAE 2.35%** ⭐ | baseline đè bẹp mọi model |

---

## 3. Vì sao? — Phân tích

**Nowcasting thắng (0.61%):** `feature[cycle t] → SOH[cycle t]` là hàm gần-tất-định
của vật lý (hình dạng đường xả ↔ dung lượng), độc lập với pin → transfer cross-battery.

**Forecasting thua:** `feature[quá khứ] → SOH[tương lai]` đòi hỏi đoán **tốc độ lão hóa
tương lai** — không suy ra được từ feature, phụ thuộc từng pin. Với chỉ 3 pin để học,
không khái quát nổi. Và vì SOH đổi chậm, **persistence (2.35%) đã quá tốt** → ML không
thêm được gì.

**Thêm pin phản tác dụng:** 21 pin thêm phủ SOH 0–122% ở điều kiện nhiệt độ/tải khác →
phân bố train lệch hẳn B0018 (67–86%) → model under-predict → 42%. Delta cũng không cứu
vì pin xả sâu có delta khổng lồ (−30…−60%) đầu độc target.

**"4 pin quá ít?"** — Tùy task: ĐỦ cho nowcasting (bằng chứng 0.61%), thiếu cho
forecasting/RUL. Nhưng thêm data không giúp vì forecasting vốn bị persistence đè.

---

## 4. Code đã xây (tái dùng được)

- `src/models/rul_predictor.py` — cycle-sequence regressor (tái dùng `MambaBlock`)
- `scripts/preprocess_rul.py` — dataset RUL + per-battery windows (LOBO)
- `scripts/preprocess_forecast.py` — dataset forecast (lookback→future SOH + anchor),
  hỗ trợ `--batteries all` (toàn bộ 34 pin)
- `scripts/train.py` — `train_rul`, `_lobo` (generic LOBO), `train_forecast_lobo`,
  `train_forecast_delta` (anchor + persistence baseline)
- Tests: `tests/test_rul.py` (8) + `tests/test_forecast.py` (3) — PASS

**Lệnh tái lập:**
```bash
python scripts/preprocess_rul.py
python scripts/train.py --rul --epochs 100          # RUL fixed split
python scripts/train.py --lobo --epochs 100         # RUL leave-one-battery-out
python scripts/preprocess_forecast.py --batteries all
python scripts/train.py --forecast --holdout B0018 --epochs 100            # absolute
python scripts/train.py --forecast --delta --holdout B0018 --epochs 100    # delta + multi-battery
```

---

## 5. Khuyến nghị

1. **Giữ nowcasting (window=30, 0.61%) làm model SOH chính thức** — đã đạt target.
2. **Báo cáo KLTN:** trình bày long-context như một hướng *đã khảo sát có hệ thống*, với
   bảng kết quả + phân tích persistence — một negative result có cơ sở khoa học.
3. Nếu muốn theo đuổi forecasting nghiêm túc về sau: cần dataset nhiều pin **cùng điều
   kiện** + chuẩn hóa per-condition; ngoài phạm vi NASA-4-pin hiện tại.
