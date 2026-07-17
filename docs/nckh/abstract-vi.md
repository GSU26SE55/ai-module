# Abstract (tiếng Việt)

> Bản gốc user viết 03/07. Cập nhật 13/07 theo 4 quyết định chốt 07/07:
> headline 1.63→1.52 / RMSE 2.09→1.97 (bắt buộc); thêm "chéo nhiệt độ"
> khớp luận điểm protocol khó xuyên suốt §4–§5 (gợi ý, đã áp dụng); nêu
> con số latency cụ thể 56ms bên cạnh ngưỡng <100ms (gợi ý, đã áp dụng).
> 57-dim và tách 2 cấu hình model đã đúng từ bản gốc, không cần sửa.

Sự phát triển nhanh chóng của các hệ thống năng lượng mặt trời đòi hỏi việc
giám sát pin lithium-ion phải thực sự đáng tin cậy, bởi sự suy giảm dung
lượng nếu không được phát hiện sẽ tiềm ẩn những rủi ro nghiêm trọng về kinh
tế và an toàn. Mặc dù Trạng thái Sức khỏe (State of Health – SOH) là chỉ số
cốt lõi để đánh giá tình trạng pin, việc ước lượng chính xác chỉ số này
theo thời gian thực từ dữ liệu cảm biến thô vẫn là một thách thức lớn về
mặt tính toán và phương pháp luận. Các mạng hồi quy truyền thống gặp khó
khăn trong việc nắm bắt các phụ thuộc thời gian dài hạn vốn có trong chu kỳ
suy giảm của pin, trong khi các kiến trúc dựa trên Transformer lại đòi hỏi
chi phí tính toán quá lớn để có thể triển khai trên các thiết bị biên (edge
deployment). Để giải quyết những hạn chế trên, bài báo này đề xuất
MambaSOHPredictor, một khung mô hình (framework) gọn nhẹ tận dụng Mô hình
Không gian Trạng thái Chọn lọc (Selective State Space Model – SSM) Mamba,
kết hợp với kỹ thuật điều chuẩn đặc trưng phổ dựa trên thông tin vật lý
(physics-informed spectral feature conditioning), được triển khai theo hai
cấu hình: cấu hình chuỗi dài (L = 4096) xử lý toàn bộ chu kỳ phóng nhằm tối
ưu độ chính xác, và cấu hình tinh gọn 30 bước phục vụ suy diễn thời gian
thực trên thiết bị biên. Kiến trúc đề xuất xử lý dữ liệu chuỗi thời gian đa
biến (điện áp, dòng điện, nhiệt độ) thông qua các lớp MambaBlock — đạt độ
phức tạp tuyến tính O(L) — và tích hợp một véc-tơ đặc trưng 57 chiều gồm
các thông số thống kê và phổ thông qua cơ chế Điều chế Tuyến tính theo Đặc
trưng (Feature-wise Linear Modulation – FiLM). Hơn nữa, độ bất định của dự
đoán (prediction uncertainty) được định lượng một cách mạnh mẽ thông qua
Monte Carlo Dropout, trong khi việc phát hiện bất thường được thực hiện
đồng thời bằng thuật toán Isolation Forest hoạt động trong cùng không gian
đặc trưng, kết hợp với các mức trạng thái sức khỏe suy ra từ SOH để hợp
thành ma trận rủi ro phục vụ ưu tiên bảo trì. Được đánh giá trên Tập dữ
liệu Pin của NASA Ames với giao thức kiểm thử chéo pin và chéo nhiệt độ
nghiêm ngặt (pin kiểm thử được cô lập hoàn toàn khỏi quá trình huấn luyện),
cấu hình chuỗi dài đạt Sai số Tuyệt đối Trung bình (MAE) là 1.52% và Căn
bậc hai Sai số Toàn phương Trung bình (RMSE) là 1.97% đối với bài toán ước
lượng SOH, vượt qua các ngưỡng vận hành tiêu chuẩn. Song song đó, cấu hình
tinh gọn hoàn thành toàn bộ chu trình suy diễn (inference pipeline) trên
CPU trong chưa tới 100 ms (trung bình 56 ms), chứng minh tính khả thi của
khung mô hình trong việc bảo trì dự đoán trên thiết bị theo thời gian thực
mà không cần phụ thuộc vào khả năng tăng tốc của GPU.

---

## Còn thiếu (theo yêu cầu bản 03/07 — không chặn, cần làm trước khi nộp)

- **Bản tiếng Anh** — chưa dịch, nằm trong kế hoạch dịch chung cả bài (15–16/7).
- **Keywords** — chưa có, cần thêm 4–6 từ khóa cuối abstract theo chuẩn IEEE
  (gợi ý: *Mamba, state space model, battery state of health, FiLM, cross-battery
  generalization, predictive maintenance*).
