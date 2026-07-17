# Section 6 — Conclusion & Acknowledgment (bản nháp tiếng Việt)

> Viết 12/07 dựa trên số liệu chốt tại §4 và lập luận tại §5 — không có ô
> số nào phụ thuộc thí nghiệm chưa chạy.

---

## 6. Conclusion

Bài báo trình bày một kiến trúc Mamba state-space duy nhất, có hai cấu hình
phục vụ hai mục tiêu bổ sung cho nhau, được đánh giá dưới một giao thức
cross-battery, cross-temperature khó hơn cách chia theo timestep phổ biến
trong văn liệu. Dưới giao thức này — pin test B0048 hoàn toàn chưa xuất hiện
trong huấn luyện và thuộc miền nhiệt độ 4°C ít được quan sát — cấu hình
long-seq (L = 4096) đạt MAE 1.52%/RMSE 1.97%, vượt ngưỡng công nghiệp 2% và
giảm 69% sai số tương đối so với baseline CNN-LSTM cùng giao thức; cấu hình
window-30 nhẹ hơn (79k tham số) vẫn đạt MAE dưới 2% trong khi suy luận
56.1 ms trung bình (P95 78.3 ms) trên CPU thông thường, đáp ứng ràng buộc
thời gian thực cho cảnh báo ưu tiên P1. Giao thức leave-one-battery-out trên
16 pin xác nhận B0048 không phải một lựa chọn thuận lợi, đồng thời bộc lộ
một failure mode rõ ràng — sai số tăng mạnh ở các pin sống toàn bộ vòng đời
trong vùng SOH thấp hiếm gặp trong huấn luyện — mà chúng tôi cho thấy có thể
giảm bằng cách mở rộng độ phủ dữ liệu, không nhất thiết phải đổi kiến trúc.
Với phát hiện bất thường, chúng tôi báo cáo trung thực rằng IsolationForest
trên đặc trưng phổ đạt F1 khiêm tốn (0.34 trên nhãn có ý nghĩa thống kê),
phù hợp vai trò một tầng cảnh báo sớm độ nhạy cao cần xác nhận thêm bởi con
người, hơn là một bộ phân loại tự động hoàn chỉnh — một giới hạn chúng tôi
nêu rõ thay vì che giấu.

Nhìn chung, kết quả cho thấy độ chính xác đạt chuẩn công nghiệp và khả năng
triển khai thời gian thực có thể cùng tồn tại trong một kiến trúc nhẹ, cài
đặt hoàn toàn bằng PyTorch thuần không phụ thuộc CUDA kernel chuyên dụng —
với điều kiện được đánh giá trung thực dưới một giao thức đủ khó để phản
ánh khả năng tổng quát hóa thật. Hướng phát triển tiếp theo gồm mở rộng dữ
liệu huấn luyện theo các tổ hợp (nhiệt độ × SOH) còn thưa, dự đoán RUL, kết
hợp SOH và anomaly thành ma trận rủi ro phục vụ ra quyết định bảo trì, và
lớp prescription dựa trên RAG — các thành phần này nằm ngoài phạm vi bài
báo nhưng đang được phát triển trong hệ thống giám sát pin solar mà nhóm
hướng tới.

## 7. Acknowledgment

Nhóm tác giả xin chân thành cảm ơn giảng viên hướng dẫn, Thầy Trương Long,
vì những góp ý và định hướng trong suốt quá trình thực hiện nghiên cứu này.
Nghiên cứu sử dụng bộ dữ liệu công khai NASA Ames Prognostics Center for
Battery Data [cite: Saha & Goebel] — xin cảm ơn đơn vị đã chia sẻ dữ liệu
phục vụ cộng đồng nghiên cứu.

---

## Ghi chú thực thi (không đưa vào bài)

- §6 tổng hợp đúng 3 luận điểm đã chốt trong plan (protocol khó + kiến trúc
  nhẹ + kết quả đạt chuẩn) + 1 đoạn thừa nhận hạn chế anomaly, tránh lặp
  nguyên văn §5.
- §7 giữ ngắn theo chuẩn IEEE (2–3 câu). Cần xác nhận: (a) chính tả đầy đủ
  tên GVHD (danh xưng "Thầy Trương Long" hay cần họ tên đầy đủ + học hàm/học
  vị theo yêu cầu venue); (b) có cần thêm dòng cảm ơn Khoa/Trường FPT
  University theo mẫu NCKH sinh viên không — venue cụ thể sẽ quyết định.
## Back-matter (bổ sung 13/07)

### Data Availability

Nghiên cứu sử dụng bộ dữ liệu công khai Battery Data Set của NASA Ames
Prognostics Data Repository [Saha & Goebel, 2007], truy cập được tại trang
chính thức của NASA Prognostics Center of Excellence. Mã nguồn tiền xử lý,
huấn luyện và các script tái tạo bảng/hình của bài báo được lưu trong
repository của nhóm `[CHỌN 1: (a) công khai tại github.com/GSU26SE55/ai-module —
nếu quyết định public repo; (b) "và cung cấp theo yêu cầu" (available upon
request) — nếu giữ private]`. Toàn bộ thí nghiệm dùng random seed 42; mỗi
con số trong bài truy vết được về file log và commit tương ứng.

### AI-Usage Disclosure

Nhóm tác giả sử dụng công cụ AI (Claude, Anthropic) hỗ trợ trong quá trình
thực hiện: soạn khung bản nháp các phần văn bản từ số liệu thí nghiệm do
nhóm chạy và cung cấp, viết script vẽ hình từ dữ liệu, tra cứu và tổng hợp
tài liệu tham khảo (các trích dẫn được nhóm kiểm chứng lại theo nguồn gốc),
và rà soát tính nhất quán giữa mô tả phương pháp với mã nguồn. Toàn bộ
thiết kế nghiên cứu, thực nghiệm, số liệu, các quyết định khoa học và nội
dung cuối cùng do nhóm tác giả thực hiện, kiểm chứng và chịu trách nhiệm.
`[Lưu ý: kiểm tra mẫu quy định AI-usage của venue nộp bài — nếu venue có
form riêng thì điền theo form đó, đoạn này là bản mặc định theo thông lệ
IEEE/ACM.]`

### Author Contributions (CRediT) — ⬜ CHỜ USER

Cần danh sách: họ tên đầy đủ từng tác giả + vai trò theo CRediT taxonomy
(Conceptualization, Methodology, Software, Validation, Writing — original
draft, Writing — review & editing, Supervision...). Chưa viết được vì chưa
có danh sách tác giả chính thức (cùng thông tin cần cho §9 Biography).

---

- ⬜ **Còn thiếu theo mandatory back-matter trong `nckh-paper-plan.md`**
  (chưa được yêu cầu viết, liệt kê ở đây để không quên): **Data Availability**
  (dataset NASA công khai + repo GitHub), **AI-usage disclosure** (skill
  `academic-research-skills:ars-disclosure` có thể tạo), **Author
  Contributions** (CRediT taxonomy — cần danh sách vai trò từng thành viên,
  cùng thông tin cần cho §9 Biography).
