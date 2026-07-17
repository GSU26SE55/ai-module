# Section 5 — Discussion (bản nháp tiếng Việt)

> Viết 11/07, cập nhật 12/07 sau khi Table 3 (ablation) đủ số và sau khi
> verify trực tiếp full-text SambaMixer (user cung cấp). Không còn ô `[x.xx]`
> nào phụ thuộc thí nghiệm chưa chạy — mọi số liệu đã dùng đều có nguồn
> trong §4. ⬜ còn lại chỉ là việc không chặn viết (literature matrix cho
> §2, verify DOI cuối cho References — xem bảng "Nguồn" cuối file).

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
Việc điều biến FiLM bằng vector phổ 57 chiều (tính trên toàn chu kỳ, áp dụng
sau attention pooling lên biểu diễn chu kỳ đã tổng hợp — không phải theo
từng token, xem §3.3) là kênh duy nhất trong mô hình long mang thông tin
toàn cục dạng phổ vào dự đoán cuối cùng. Ablation thành phần (Bảng 3, §4.4a)
củng cố trực tiếp lập
luận này ở phần tổng hợp toàn cục: thay attention pooling — cơ chế duy nhất
đọc được toàn bộ 511 token — bằng lấy token cuối làm MAE tăng +0.41 điểm
phần trăm (+27% tương đối), mức tăng lớn nhất trong ba biến thể ablation.
Đây là bằng chứng thực nghiệm, không chỉ suy luận từ thiết kế, rằng thông
tin toàn cục cần được tổng hợp tường minh chứ không thể suy ra từ trạng
thái cục bộ ở cuối chuỗi. Ablation riêng cho FiLM (bỏ hẳn điều biến phổ,
không chỉ đổi cách tổng hợp) không nằm trong phạm vi 3 thí nghiệm đã chạy —
đây vẫn là một giới hạn thực nghiệm, ghi nhận ở §5.4.

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
thuộc CUDA kernel chuyên dụng.

Chúng tôi cũng không claim là công trình đầu tiên áp dụng Mamba cho dự đoán
SOH pin. Công trình gần nhất là SambaMixer [Olalde-Verano, Kirch, Pérez-Molina
& Martín, *IEEE Access*, vol. 13, 2025, tr. 2313–2324+], cũng dùng kiến trúc
Mamba (MambaMixer — selective SSM có channel-mixing) trên NASA battery
dataset với giao thức cross-battery: cấu hình lớn nhất của họ (NASA-L) huấn
luyện trên 10 pin (#5, 18, 31, 34, 36, 45, 48, 54, 55, 56) và đánh giá trên
3 pin hoàn toàn tách biệt (#6, #7, #47). Trên các pin có thể đối chiếu,
SambaMixer đạt MAE thấp hơn kết quả của chúng tôi (0.512–1.197% tùy pin test
— tự báo cáo giảm 52% MAE so với các baseline CNN/RNN trước đó, so với 1.52%
của mô hình long-seq chúng tôi) — chúng tôi không claim vượt trội về độ
chính xác thuần túy. Khác biệt nằm ở quy mô và tính triển khai được: mô hình
lớn nhất của họ (SambaMixer-L) có 48.7 triệu tham số (~490 lần mô hình
long-seq của chúng tôi, 99 nghìn tham số) và bài không báo cáo độ trễ suy
luận hay khả năng chạy trên thiết bị biên. Đóng góp của chúng tôi là đạt
ngưỡng chính xác công nghiệp (MAE < 2%) ở quy mô nhỏ hơn nhiều bậc, với độ
trễ CPU đã đo và xác nhận <100 ms (§4.5).

Đáng chú ý, hai phát hiện độc lập của SambaMixer củng cố trực tiếp hai quan
sát của chính chúng tôi. Thứ nhất, nhóm tác giả báo cáo sai số lớn bất
thường khi dự đoán SOH trên 92% cho pin #06, và giả thuyết nguyên nhân là
tập huấn luyện của họ không có mẫu nào ở vùng SOH đó — cùng cơ chế thất bại
mà chúng tôi quan sát ở dải 80–90% (§4.4b, §5.2), từ một nhóm nghiên cứu độc
lập trên cùng họ dữ liệu NASA. Thứ hai, thí nghiệm scaling model của họ cho
thấy tăng từ SambaMixer-L lên XL (85.6M tham số) làm giảm hiệu năng, với
giả thuyết overfitting trên tập dữ liệu nhỏ — song song với phát hiện của
chúng tôi ở Bảng 3 rằng giảm d_state từ 32 xuống 16 lại cải thiện MAE trên
B0048 (§4.4a). Cả hai điểm song song này gợi ý rằng giới hạn về năng lực dữ
liệu (chỉ vài chục pin NASA) — không phải lựa chọn kiến trúc cụ thể — là
yếu tố giới hạn chung của cả hai công trình.

Một công trình Transformer gần đây, TIDSIT [Patel, Ramezankhani, Deodhar,
Birru, arXiv:2507.18320, 2025], cũng đánh giá theo giao thức cross-battery
trên chính NASA dataset (huấn luyện trên B0005 và B0006, kiểm thử trên
B0007) và báo cáo RMSE 0.58% trên pin test — thấp hơn kết quả của chúng
tôi. Tuy nhiên quy mô đánh giá của họ nhỏ hơn đáng kể: chỉ 3 pin tham gia
toàn bộ thí nghiệm (2 train, 1 test), không có kiểm định robustness kiểu
LOBO, và không công bố số tham số hay độ trễ suy luận. Chúng tôi nêu công
trình này với cùng tinh thần như SambaMixer: không tranh cãi con số tuyệt
đối, mà làm rõ rằng độ nghiêm ngặt của giao thức đánh giá (26 pin, LOBO
16 fold, ablation trung thực) là một trục đóng góp độc lập với độ chính
xác thô.

**Bảng 6 — So sánh với các công trình cross-battery gần nhất trên NASA dataset.**

| Công trình | Kiến trúc | Tham số | Giao thức | MAE | Latency | Robustness |
|---|---|---:|---|---:|---|---|
| SambaMixer-L (2025) | MambaMixer | 48.7M | 10 pin train / 3 eval | 0.51–1.20% | Không báo cáo | Không |
| TIDSIT (2025) | Transformer | Không công bố | 2 pin train / 1 eval | 0.58% | Không báo cáo | Không |
| **Mô hình long (bài này)** | Mamba + FiLM | **99k** | **23 pin train / 2 val / 1 test** | **1.52%** | Không đo (§4.5 đo bản window-30) | **LOBO 16 fold** |
| **Mô hình window-30 (bài này)** | Mamba + FiLM | **79k** | Cùng trên | 1.98% | **56.1 ms (P95 78.3 ms)** | — |

Bảng cho thấy rõ trục đánh đổi: hai công trình đối chứng đạt MAE thấp hơn
nhưng không công bố quy mô tham số đầy đủ hoặc độ trễ, và đánh giá trên ít
pin hơn đáng kể (3 và 1 pin tương ứng so với 26 pin của bài này); phía
chúng tôi đạt ngưỡng công nghiệp ở quy mô nhỏ hơn nhiều bậc, có đo latency
thật và có kiểm định robustness qua nhiều fold.

Vị trí đầy đủ trong văn liệu Mamba-battery (gồm cả MambaLithium, U-H-Mamba,
multimodal Mamba-battery, và Crocioni et al. — công trình về triển khai
model nhỏ trên thiết bị nhúng, gần với hướng deployability của chúng tôi)
sẽ hoàn thiện ở Related Work (§2).

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
