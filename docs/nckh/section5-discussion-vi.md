# Section 5 — Discussion (bản nháp tiếng Việt)

> Viết 11/07 dựa trên số liệu đã có ở §4 (Table 1, 2, 3b, 5). Không có ô
> `[x.xx]` nào phụ thuộc thí nghiệm chưa chạy — phần duy nhất chờ là 1 câu
> tùy chọn ở §5.1 nếu Table 3 (component ablation) có số trước khi chốt bài.
> ⬜ = việc cần làm nhưng không chặn viết (trích dẫn, đối chiếu số liệu).

---

## 5.1 Vì sao kiến trúc và giao thức này hiệu quả

Khoảng cách sai số giữa CNN-LSTM (MAE 4.90%) và Mamba window-30 cùng
protocol (1.98%) — cùng kích thước đầu vào, cùng tập huấn luyện, khác duy
nhất kiến trúc — cho thấy phần lớn cải thiện đến từ khả năng của SSM chọn
lọc (selective SSM) trong việc giữ lại trạng thái liên quan đến suy thoái
qua nhiều bước thời gian, thay vì cơ chế cổng cố định của LSTM. Với mô hình
long-seq, việc giảm thêm xuống 1.52% khi mở rộng cửa sổ quan sát từ 30 bước
lên toàn bộ chu kỳ (L = 4096) gợi ý rằng tín hiệu suy thoái không nằm gọn
trong một đoạn ngắn của đường cong xả, mà trải rộng theo hình dạng toàn cục
của điện áp/dòng điện — điều mà kiến trúc cửa sổ ngắn buộc phải bỏ qua.
Việc điều biến FiLM bằng vector phổ 57 chiều (tính trên toàn chu kỳ) là
kênh duy nhất trong mô hình long mang thông tin toàn cục này vào biểu diễn
cục bộ theo token; `[⬜ nếu Table 3 có số trước khi chốt bài: dẫn Δ MAE khi
bỏ attention pooling / giảm d_state để định lượng đóng góp — hiện diễn giải
này dựa trên thiết kế kiến trúc, chưa có ablation trực tiếp cho riêng FiLM
trong phạm vi thí nghiệm đã chạy]`.

Về mặt giao thức, việc B0048 — pin test chính — đạt MAE 1.47% trong LOBO
(Bảng 2, §4.3), gần như trùng khớp với Table 1 (1.52% với mô hình long),
là bằng chứng trực tiếp rằng kết quả headline không phải một lựa chọn thuận
lợi ngẫu nhiên. Đồng thời, 9/16 fold LOBO đạt MAE ≤ 2.3% cho thấy mức hiệu
năng này khái quát hóa tốt trên phần lớn miền dữ liệu — chứ không phải một
điểm số cá biệt.

## 5.2 Mô hình sai ở đâu — tổng hợp hai phân tích lỗi

Hai phân tích độc lập ở §4 cùng chỉ về một điểm yếu duy nhất: mô hình đáng
tin cậy trong vùng dữ liệu "bình thường" của tập huấn luyện, nhưng suy giảm
rõ rệt khi phải ngoại suy sang các *regime* ít được quan sát.

- **LOBO (§4.3)** cho thấy sai số lớn tập trung ở các pin sống toàn bộ vòng
  đời trong vùng SOH thấp (B0045: chưa từng vượt 54% SOH; B0033, B0054–56
  tương tự) — khi các pin này bị giữ lại làm test, phần dữ liệu huấn luyện
  còn lại gần như không có ví dụ nào ở vùng SOH đó.
- **Phân tích theo dải SOH (§4.4b)** cho thấy điều ngược lại về hướng: dải
  SOH *cao* (80–90%) của pin 4°C mới là nơi mô hình yếu nhất trong protocol
  chính (bias −4.57%), vì tập huấn luyện gốc thiếu ví dụ 4°C ở vùng SOH cao.

Cả hai đều là cùng một hiện tượng nhìn từ hai phía: **độ chính xác của mô
hình tỉ lệ thuận với độ phủ của tập huấn luyện tại vùng (nhiệt độ × SOH)
tương ứng**, không phải một hạn chế cố hữu của kiến trúc. Bằng chứng ủng hộ
trực tiếp: chỉ bằng cách bổ sung một pin 4°C phủ vùng SOH cao (B0047) vào
huấn luyện — không đổi kiến trúc, không đổi siêu tham số — MAE trên chính
dải 80–90% cải thiện từ 100% mẫu bị phân loại nhầm dưới ngưỡng EOL xuống
còn 7/16 (§4.4b). Điều này định vị lại câu hỏi "làm sao cải thiện mô hình"
thành "làm sao mở rộng độ phủ dữ liệu" — một hướng cải tiến rẻ hơn nhiều so
với thay đổi kiến trúc.

## 5.3 Định vị so với văn liệu — không claim SOTA

Chúng tôi không so sánh trực tiếp con số MAE của mình với các nghiên cứu
Mamba-battery hoặc CNN-LSTM/Transformer khác đã công bố, vì phần lớn dùng
giao thức chia theo timestep trong cùng một pin (§4.2) — giao thức này cho
phép mô hình "nhìn thấy" đặc điểm riêng của từng pin trong huấn luyện, nên
điểm số thường thấp hơn đáng kể so với giao thức cross-battery ở đây một
cách không thể so sánh trực tiếp. Đóng góp của bài không phải "đạt sai số
thấp nhất từng công bố", mà là ba điều: (i) đạt ngưỡng MAE < 2% *dưới một
giao thức đánh giá khó hơn*; (ii) một kiến trúc duy nhất cung cấp cả cấu
hình độ chính xác cao (long) lẫn cấu hình triển khai thời gian thực
(window-30, §4.5); (iii) toàn bộ cài đặt bằng PyTorch thuần, không phụ
thuộc CUDA kernel chuyên dụng. Chúng tôi cũng không claim là công trình đầu
tiên áp dụng Mamba cho dự đoán SOH pin — vị trí của bài trong văn liệu
Mamba-battery hiện có sẽ được làm rõ ở Related Work (§2) ⬜ *cần literature
matrix*.

## 5.4 Hạn chế (Limitations)

Chúng tôi liệt kê trung thực các hạn chế đã biết, thay vì để reviewer tự
tìm ra:

1. **Một pin test cho kết quả headline.** Bảng 1 chỉ đo trên B0048. Chúng
   tôi giảm nhẹ rủi ro này bằng giao thức LOBO (§4.3, 16 fold) xác nhận
   B0048 không phải lựa chọn thuận lợi, nhưng LOBO tự nó cũng cho thấy
   phương sai đáng kể giữa các pin (std 3.27%) — kết quả headline nên được
   đọc cùng với khoảng phương sai này, không phải như một con số tuyệt đối.

2. **Dữ liệu phòng thí nghiệm, chưa phải telemetry thực địa.** NASA dataset
   đo chu kỳ sạc–xả có kiểm soát trong buồng nhiệt độ cố định. Pin trong
   ứng dụng thực tế (ví dụ hệ giám sát solar backup mà nhóm hướng tới) chịu
   pattern sạc/xả không đều, nhiệt độ dao động theo môi trường, và — quan
   trọng hơn — cấu hình điện áp khác (pack nhiều cell nối tiếp thay vì một
   cell 18650 đơn). Việc triển khai đòi hỏi quy đổi điện áp pack-to-cell và
   một tầng phát hiện dữ liệu ngoài phân phối (out-of-distribution) trước
   khi tin vào dự đoán — đây là hướng phát triển đang triển khai riêng
   ngoài phạm vi bài báo này.

3. **Không có baseline Transformer cùng protocol.** Lựa chọn Mamba dựa trên
   lập luận độ phức tạp O(L) so với O(L²) của self-attention tại L = 4096
   (§3.3), được củng cố gián tiếp bởi việc CNN-LSTM — vốn cũng gặp khó khăn
   với chuỗi dài — thua kém rõ rệt trong Bảng 1. Tuy nhiên đây là suy luận
   gián tiếp, không phải phép so sánh trực tiếp; huấn luyện một baseline
   Transformer cùng giao thức là việc chưa thực hiện được trong ngân sách
   tính toán hiện tại.

4. **Nhãn bất thường là proxy, không phải chú giải lỗi thật.** Như đã nêu ở
   §4.6, cả hai định nghĩa nhãn (rate-based, EOL-based) đều suy ra từ chính
   đường cong dung lượng, không phải quan sát độc lập về lỗi cảm biến hay
   sự cố vật lý. F1 = 0.34 trên tập test (nhãn rate-based, đã tinh chỉnh)
   nên được hiểu là mức độ tách biệt giữa các *regime* suy thoái, không
   phải năng lực phát hiện lỗi thực địa.

5. **Ngoại suy ngoài miền huấn luyện chưa được kiểm soát bằng cơ chế minh
   bạch.** Cả hai phân tích lỗi ở §5.2 cho thấy mô hình xuống cấp âm thầm
   khi gặp vùng (nhiệt độ × SOH) ít dữ liệu, thay vì báo hiệu rõ ràng mức
   độ không chắc chắn tăng lên tương ứng — mặc dù MC Dropout (§3.3) cung
   cấp một tín hiệu uncertainty, chúng tôi chưa đánh giá định lượng liệu
   `soh_std` có tăng đúng tại các vùng sai số cao này hay không
   ⬜ *phân tích bổ sung nếu còn thời gian, không bắt buộc cho bản nộp*.

## 5.5 Hướng phát triển

Ba hướng tiếp nối trực tiếp từ các hạn chế trên: (i) mở rộng dữ liệu huấn
luyện theo hướng data-centric đã chứng minh hiệu quả ở §5.2, ưu tiên các tổ
hợp (nhiệt độ × SOH) còn thưa; (ii) huấn luyện và đánh giá baseline
Transformer cùng giao thức để có phép so sánh trực tiếp; (iii) chuyển từ
nhãn bất thường proxy sang dữ liệu gán nhãn bán giám sát khi có telemetry
thực địa từ thiết bị IoT. Ngoài phạm vi bài báo, các hướng liên quan trong
hệ thống capstone gồm: dự đoán RUL (remaining useful life), tầng kết hợp
SOH + anomaly thành ma trận rủi ro phục vụ ra quyết định bảo trì, và lớp
prescription dựa trên RAG.

---

## Nguồn số liệu tham chiếu (không đưa vào bài)

| Claim | Nguồn |
|-------|-------|
| CNN-LSTM 4.90% vs Mamba w30 1.98% vs long 1.52% | Table 1, `docs/nckh/section4-experiments-vi.md` §4.2 |
| B0048 LOBO fold = 1.47%, 9/16 fold ≤ 2.3% | Table 2, §4.3 |
| B0045 SOH range [0, 54.1]% và các pin outlier khác | §4.3, đã verify từ `metadata.csv` (phiên 07/07) |
| Per-band bias −4.57% ở 80–90%, cải thiện v1.5→v1.6 (100%→7/16) | Table 3b, §4.4b, nguồn `logs/GH-88/ablation.md` |
| Anomaly F1 = 0.34 test (rate label, tuned) | Table 5, §4.6, `logs/nckh/anomaly/table5.md` |
| Latency 56.1ms / 78.3ms P95 | Table 4, §4.5 |
| Split protocol khác nhau giữa nghiên cứu (timestep vs battery) | `docs/nckh-paper-plan.md` — cần literature matrix để trích dẫn cụ thể ⬜ |
