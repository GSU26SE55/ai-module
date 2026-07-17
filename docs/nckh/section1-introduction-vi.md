# Section 1 — Introduction (bản nháp tiếng Việt)

> Viết 13/07. Gap statement dùng bằng chứng THẬT (SambaMixer, TIDSIT đã
> verify ở §5.3/literature-matrix.md) thay vì suy đoán chung chung như bản
> plan gốc — mạnh hơn vì có số liệu cụ thể để trích dẫn.
> ⬜ = chờ literature matrix đủ để trích thêm 1–2 câu mở đầu (không chặn nộp).

---

Pin lithium-ion là công nghệ lưu trữ năng lượng phổ biến nhất hiện nay, từ
thiết bị điện tử cầm tay đến xe điện và hệ thống lưu trữ năng lượng tái tạo.
Trong các hệ thống lưu trữ năng lượng mặt trời (solar backup) — bối cảnh
ứng dụng của nghiên cứu này — pin không chỉ cần hiệu suất cao mà còn phải
được giám sát liên tục để tránh hỏng hóc bất ngờ, vì chi phí thay thế và
rủi ro an toàn (quá nhiệt, cháy nổ) đều lớn hơn nhiều so với thiết bị tiêu
dùng thông thường. Dự đoán chính xác **trạng thái sức khỏe** (State of
Health, SOH) — tỉ lệ dung lượng hiện tại so với dung lượng định mức — là
điều kiện tiên quyết để chuyển từ bảo trì theo lịch sang bảo trì dự đoán
(predictive maintenance), giúp lên kế hoạch thay thế trước khi pin xuống
dưới ngưỡng an toàn.

Các phương pháp truyền thống dựa trên mô hình mạch điện tương đương
(equivalent circuit model) kết hợp bộ lọc Kalman ước lượng SOH thông qua
tham số vật lý của pin, nhưng đòi hỏi hiệu chỉnh mô hình mạch điện cẩn thận
và suy giảm độ chính xác khi điều kiện vận hành thay đổi. Học sâu (LSTM,
CNN-LSTM, gần đây là Transformer) đã trở thành hướng tiếp cận phổ biến hơn
nhờ khả năng học trực tiếp từ dữ liệu telemetry mà không cần mô hình vật lý
tường minh. Tuy nhiên, kiến trúc Transformer — dù mạnh trong việc nắm bắt
phụ thuộc dài hạn — có chi phí tính toán O(L²) theo độ dài chuỗi L, khiến
việc đưa toàn bộ tín hiệu thô của một chu kỳ xả (hàng nghìn điểm đo) vào mô
hình trở nên tốn kém; phần lớn công trình vì vậy chỉ dùng cửa sổ ngắn hoặc
đặc trưng đã được rút gọn thủ công. Đáng chú ý hơn, nhiều nghiên cứu đánh
giá mô hình bằng cách chia tập huấn luyện/kiểm thử theo *thời điểm* trong
cùng một pin — một giao thức cho phép mô hình "nhìn thấy" đặc điểm riêng
của chính pin đang được kiểm thử, dẫn đến sai số công bố thấp hơn đáng kể
so với khi mô hình phải tổng quát hóa sang một pin hoàn toàn chưa từng thấy.

Mamba — một họ mô hình không gian trạng thái có tính chọn lọc (selective
state space model) — gần đây nổi lên như một lựa chọn thay thế Transformer
cho dữ liệu chuỗi dài, với độ phức tạp tuyến tính O(L) mà vẫn giữ được khả
năng nắm bắt phụ thuộc xa. Đặc tính này phù hợp trực tiếp với bài toán SOH:
một chu kỳ xả đầy đủ có thể dài hàng nghìn điểm đo, và Mamba cho phép đưa
toàn bộ tín hiệu đó vào mô hình mà không phải trả chi phí bậc hai của
attention. Một số công trình gần đây đã bắt đầu áp dụng Mamba cho dự đoán
SOH pin — đáng chú ý nhất là SambaMixer [Olalde-Verano et al., IEEE Access
2025], đạt độ chính xác cao trên chính bộ dữ liệu NASA mà nghiên cứu này sử
dụng, bằng một mô hình 48.7 triệu tham số không công bố độ trễ suy luận hay
khả năng triển khai. Một hướng khác, TIDSIT [Patel et al., 2025], dùng
Transformer trên giao thức cross-battery của NASA nhưng chỉ đánh giá trên
3 pin (2 huấn luyện, 1 kiểm thử), không kiểm định độ vững chắc qua nhiều
tổ hợp huấn luyện/kiểm thử khác nhau.

Khoảng trống chúng tôi xác định không nằm ở việc "chưa ai dùng Mamba cho
pin", mà ở chỗ **chưa công trình nào kết hợp đồng thời ba yêu cầu**: (i)
một giao thức đánh giá đủ nghiêm ngặt — cross-battery *và* cross-temperature,
với kiểm định độ vững chắc qua nhiều fold thay vì một phép chia cố định;
(ii) một kiến trúc đủ nhẹ để triển khai thời gian thực, không chỉ tối ưu
độ chính xác thô; và (iii) báo cáo trung thực về nơi mô hình thất bại, thay
vì chỉ công bố con số tổng hợp tốt nhất. Bài báo này đề xuất một kiến trúc
Mamba duy nhất, patch-based, điều biến FiLM trên đặc trưng phổ mức chu kỳ,
dự đoán SOH pin lithium-ion từ telemetry thô đầy đủ một chu kỳ (L = 4096)
với MAE 1.52% dưới một giao thức đánh giá cross-battery, cross-temperature
nghiêm ngặt (pin 4°C hoàn toàn tách biệt) — trong khi một biến thể gọn nhẹ
30 bước thời gian duy trì suy luận CPU dưới 100 ms cho triển khai thời gian
thực.

Đóng góp chính của bài báo gồm ba điểm:

1. **Kiến trúc**: mô hình Mamba cài đặt thuần PyTorch (không phụ thuộc
   CUDA kernel chuyên dụng) với patch encoder nén chuỗi L = 4096 thành 511
   token, điều biến FiLM trên vector đặc trưng phổ 57 chiều (bao gồm hệ số
   Gini và kurtosis), cùng hai kênh dẫn xuất — đường cong dung lượng gia
   tăng (IC curve) và tiến độ xả.
2. **Giao thức đánh giá**: chia dữ liệu theo pin (cross-battery) trên bộ
   NASA Ames (26 pin), với tập validation/test là các pin 4°C mô hình chưa
   từng quan sát, kèm kiểm định leave-one-battery-out trên 16 fold để báo
   cáo độ vững chắc dưới dạng mean ± std thay vì một con số đơn lẻ.
3. **Ý thức triển khai**: biến thể 30 bước thời gian (~79 nghìn tham số)
   đạt suy luận <100 ms trên CPU thông thường — khả thi cho giám sát pin
   solar thời gian thực, một khía cạnh chưa được các công trình Mamba-battery
   hiện có báo cáo tường minh.

---

## Nguồn/ghi chú (không đưa vào bài)

| Claim | Nguồn |
|-------|-------|
| SambaMixer 48.7M params, không báo cáo latency | `literature-matrix.md` 3.1, verify full-text 12/07 |
| TIDSIT 3 pin, không LOBO | `literature-matrix.md` 2.1, verify fetch 12/07 |
| Headline MAE 1.52%, L=4096→511 token, 57-dim spectral | `section3-methodology-vi.md`, `section4-experiments-vi.md` Table 1 |
| Window-30 79k params, <100ms | Table 4, §4.5 |
| Transformer O(L²) | Kiến thức nền tảng Mamba paper (Gu & Dao 2023) — ⬜ có thể trích trực tiếp câu này khi viết bản tiếng Anh |

⬜ **Việc còn lại (không chặn)**: 1–2 câu mở đầu đoạn 2 (ECM/Kalman) nên trích
1 nguồn cụ thể từ Nhóm 1 literature-matrix (1.1 hoặc 1.2) khi đã đọc xong —
hiện đang viết chung chung không có citation number.
