# Section 3 — Methodology (bản COPY-READY cho Google Docs)

> Cập nhật 17/07: thay bản draft cũ bằng đúng văn phong bản Docs của user,
> đã sửa toàn bộ lỗi số liệu/kỹ thuật (danh sách sửa ở cuối file — phần đó
> KHÔNG copy vào Docs). Công thức viết dạng text để dán thẳng; khi ráp bản
> cuối chuyển sang equation editor/LaTeX.

---

## 3.1. Tập dữ liệu và giao thức đánh giá

Nghiên cứu này sử dụng tập dữ liệu vòng đời pin lithium-ion được cung cấp bởi Trung tâm Nghiên cứu Tiên lượng xuất sắc NASA Ames (NASA Ames Prognostics Center of Excellence) [CITE: Saha & Goebel]. Tập dữ liệu bao gồm các cell pin loại 18650 có dung lượng danh định 2.0 Ah, được thực hiện chu trình phóng–sạc tuần hoàn cho đến khi dung lượng suy giảm vượt ngưỡng an toàn. Mỗi chu kỳ phóng cung cấp chuỗi dữ liệu đo lường theo thời gian thực (bao gồm điện áp, dòng điện, nhiệt độ bề mặt) và giá trị dung lượng thực tế đo được tại thời điểm kết thúc chu kỳ. Trạng thái sức khỏe (State of Health – SOH) của pin được định nghĩa dựa trên tỷ lệ dung lượng còn lại:

SOH_t = (C_t / C_nominal) × 100 %,  với C_nominal = 2.0 Ah

Trong tổng số 34 cell pin của tập dữ liệu gốc, nghiên cứu chọn lọc 26 cell pin đáp ứng các tiêu chuẩn chất lượng dữ liệu. Các mẫu bị loại trừ bao gồm: B0036 (chứa nhiễu đo lường khiến SOH vượt ngưỡng 122%), nhóm B0049–B0052 (chuỗi dữ liệu thiếu hụt hoặc gián đoạn) và nhóm B0038–B0040 (nhóm dữ liệu dự phòng). Những chu kỳ phóng bị khuyết giá trị dung lượng hoặc có độ dài quan sát ngắn hơn cửa sổ tiêu chuẩn cũng được loại bỏ khỏi tập phân tích.

Điểm khác biệt cốt lõi về mặt phương pháp luận so với các nghiên cứu tiền nhiệm — vốn thường phân chia tập dữ liệu theo bước thời gian bên trong cùng một cell pin [CITE: các bài LSTM/CNN-LSTM] — là nghiên cứu này áp dụng giao thức phân chia độc lập theo cell pin (cross-battery split). Cụ thể:

- Tập huấn luyện (Training set): 23 cell pin.
- Tập kiểm định (Validation set): 2 cell pin (B0046, B0047).
- Tập kiểm thử (Testing set): 1 cell pin (B0048) được cô lập hoàn toàn.

Quy trình này đảm bảo mỗi cell pin chỉ thuộc một tập dữ liệu duy nhất, buộc mô hình phải dự đoán trên các cell chưa từng được quan sát. Đáng chú ý, toàn bộ pin thuộc tập kiểm định và kiểm thử đều được vận hành ở điều kiện nhiệt độ môi trường khắc nghiệt (4°C) — ngưỡng nhiệt mà động học điện hóa thể hiện sự sai khác lớn so với điều kiện tiêu chuẩn. Nhằm thiết lập khả năng học đại diện cho miền nhiệt độ này thay vì nội suy tuyến tính, tập huấn luyện đã tích hợp sẵn một nhóm pin hoạt động ở 4°C (B0041, B0045, B0053–B0056). Giao thức này được thiết kế để đánh giá trực tiếp năng lực tổng quát hóa của mô hình trên các đối tượng vật lý mới và điều kiện vận hành phi tiêu chuẩn. Toàn bộ quá trình tiền xử lý và phân chia dữ liệu sử dụng hạt giống ngẫu nhiên (random seed) cố định là 42 nhằm đảm bảo tính tái lập (reproducibility) của thực nghiệm.

Để đánh giá độ vững chắc thống kê vượt ra ngoài một phép chia cố định, nghiên cứu bổ sung giao thức leave-one-battery-out (LOBO): lần lượt giữ từng cell pin làm tập kiểm thử và huấn luyện trên các cell còn lại, với bộ chuẩn hóa được khớp lại trong từng vòng lặp nhằm loại trừ rò rỉ dữ liệu (kết quả trình bày tại Mục 4.3).

## 3.2. Tiền xử lý và trích xuất đặc trưng

**Chuỗi tín hiệu đầu vào:** Mỗi chu kỳ phóng cung cấp bốn kênh biến thiên theo thời gian (điện áp, dòng điện, nhiệt độ bề mặt, mốc thời gian) và hai kênh phụ trợ được tính toán từ tín hiệu gốc nhằm gia tăng thông tin phân tích:

- Đường cong dung lượng gia tăng (Incremental Capacity – dQ/dV): Một đại lượng phân tích điện hóa kinh điển, biểu diễn mức độ lão hóa thông qua sự dịch chuyển biên độ và vị trí của các đỉnh dQ/dV [CITE: bài IC analysis].
- Tiến độ xả (Discharge progress): Tỉ lệ dung lượng đã phóng tích lũy so với tổng dung lượng của chu kỳ, nhận giá trị trong khoảng [0, 1], cung cấp tín hiệu định vị tường minh về vị trí hiện tại trong chu kỳ phóng.

Hình 1 minh họa động lực của thiết kế này: khi pin lão hóa, thay đổi xuất hiện trên toàn bộ hình dạng đường xả — thời lượng chu kỳ ngắn dần, profile nhiệt dịch chuyển, và đỉnh IC quanh 3.5 V suy giảm một cách hệ thống — tín hiệu trải khắp chu kỳ thay vì tập trung trong một cửa sổ ngắn.

Sáu kênh dữ liệu này được chuẩn hóa về khoảng [0, 1] bằng thuật toán MinMaxScaler. Để ngăn ngừa hiện tượng rò rỉ dữ liệu (data leakage), bộ chuẩn hóa chỉ được khớp (fit) duy nhất trên tập huấn luyện, sau đó áp dụng nguyên trạng bộ tham số này cho tập kiểm định, tập kiểm thử và pha suy diễn thực tế. Về cấu trúc thời gian, chuỗi phân tích toàn chu kỳ được nội suy cố định về độ dài L = 4096 bước; trong khi cấu hình tinh gọn (compact configuration) sử dụng cửa sổ trượt 30 bước không chồng lấp, phục vụ bài toán suy diễn thời gian thực (được trình bày tại Mục 3.4). Lưu ý rằng cấu hình tinh gọn sử dụng bộ sáu kênh riêng: bốn kênh đo trực tiếp cùng chỉ số chu kỳ chuẩn hóa và SOC ước lượng, thay cho hai kênh dẫn xuất của cấu hình chuỗi dài.

**Trích xuất đặc trưng phổ mức chu kỳ (Cycle-level spectral features):** Song song với chuỗi dữ liệu thô, tín hiệu của mỗi chu kỳ được nén thành một véc-tơ đặc trưng 57 chiều, bao gồm 19 chỉ số thống kê và biến đổi cho mỗi kênh (điện áp, dòng điện, nhiệt độ). Cụ thể:

- 10 đặc trưng miền tần số (áp dụng Biến đổi Fourier Nhanh – FFT): Tâm phổ, entropy phổ, tần số đỉnh, công suất đỉnh, độ phẳng phổ, tần số roll-off, năng lượng phân bổ trên ba dải tần và hệ số Gini phổ. Hệ số Gini phổ được tích hợp nhằm đo lường mức độ tập trung năng lượng: quá trình lão hóa làm tăng nội trở, dẫn đến sự phân tán năng lượng phổ rộng, làm hệ số Gini giảm. Đây là sự bổ khuyết quan trọng cho độ phẳng phổ cơ bản.
- 9 đặc trưng miền thời gian: Giá trị trung bình, độ lệch chuẩn, độ xiên (skewness), độ nhọn (kurtosis), hệ số đỉnh (crest factor), hệ số dạng sóng (waveform factor), hệ số xung (pulse factor), hệ số biên (margin factor) và biên độ đỉnh-đỉnh (peak-to-peak).

Các đặc trưng này được tính toán trên quy mô toàn bộ chu kỳ phóng (từ 200–800 điểm đo gốc) nhằm đảm bảo phổ FFT đạt độ phân giải tần số tối ưu. Các cửa sổ trượt thuộc cùng một chu kỳ sẽ chia sẻ chung véc-tơ đặc trưng chu kỳ này. Cuối cùng, không gian đặc trưng 57 chiều được chuẩn hóa dạng z-score (StandardScaler) dựa trên phân phối của tập huấn luyện.

## 3.3. Kiến trúc MambaSOHPredictor

(Hình 2: Kiến trúc tổng thể.)

**Khối xử lý lõi Mamba thuần PyTorch:** Lõi kiến trúc tính toán sử dụng mô hình Không gian Trạng thái Chọn lọc (Selective State Space Model – Mamba) [CITE: Gu & Dao 2023]. Nghiên cứu tiến hành triển khai mã nguồn thuần trên nền tảng PyTorch thay vì phụ thuộc vào thư viện CUDA mamba-ssm. Quyết định này nhằm tối ưu hóa tính khả chuyển (portability) của hệ thống, cho phép mô hình chạy độc lập trên các thiết bị Windows và thực thi suy diễn trực tiếp trên CPU.

Mỗi khối MambaBlock xử lý chuỗi đầu vào thông qua các bước tuần tự: phép chiếu mở rộng (với hệ số mở rộng E = 2), tích chập nhân quả tách kênh (depthwise causal convolution với kernel = 4), và cơ chế quét SSM chọn lọc. Tại đây, các tham số trạng thái có khả năng tự động thích ứng với cấu trúc dữ liệu:

h_t = Ā·h_{t−1} + B̄_t·x_t,   y_t = C_t·h_t,   với Ā = exp(Δ_t·A)

Trong đó, ma trận trạng thái được rời rạc hóa dựa trên tham số bước nhảy Δ_t học trực tiếp từ tín hiệu đầu vào; các ma trận B_t, C_t cũng được sinh từ chính đầu vào tại từng thời điểm. Cơ chế chọn lọc này cho phép mạng neural tự động quyết định lưu giữ hay triệt tiêu thông tin tại từng thời điểm — một đặc tính tối ưu đối với tín hiệu suy thoái pin, nơi phần lớn thời gian chu kỳ mang tính tĩnh tại và các đặc điểm lão hóa thường tập trung ở các pha chuyển tiếp. Độ phức tạp tính toán tuyến tính O(L) của khối SSM vượt trội hơn đáng kể so với cơ chế Self-Attention O(L²) của kiến trúc Transformer khi xử lý chuỗi cực dài L = 4096.

**Mã hóa phân mảnh (Patch Encoding):** Thay vì xử lý tuần tự từng điểm dữ liệu đơn lẻ trên chuỗi L = 4096, kiến trúc áp dụng chiến lược phân mảnh chuỗi thành các patch gồm 16 bước thời gian với bước trượt 8 (chồng lấp 50%), biểu diễn mỗi patch thành một token độc lập. Kỹ thuật này nén chuỗi 4096 bước xuống còn 511 token hiệu dụng trước khi đưa vào các tầng MambaBlock, kế thừa quan điểm nghiên cứu từ PatchTST [CITE: Nie et al. 2023] về việc duy trì ngữ nghĩa cục bộ đồng thời tối ưu hóa tính toán không gian. Bổ sung cho biểu diễn patch, mỗi token được cộng thêm bốn thống kê suy thoái cục bộ tính trong phạm vi patch (RMS, biên độ đỉnh-đỉnh, độ lệch chuẩn, độ nhọn) thông qua khối PatchDegradationEncoder — cung cấp ngữ cảnh động học cục bộ mà đặc trưng phổ toàn cục không thể mang lại.

**Gộp Token (Attention Pooling):** Sau hai tầng MambaBlock và lớp chuẩn hóa LayerNorm, chuỗi 511 token được tổng hợp thành một véc-tơ biểu diễn chu kỳ duy nhất thông qua cơ chế Attention Pooling (một đầu chú ý): mạng học một phân bố trọng số trên toàn bộ token, cho phép tập trung vào các pha động học mang nhiều thông tin suy thoái nhất thay vì chỉ lấy trạng thái cuối chuỗi.

**Điều biến biểu diễn thông qua cơ chế FiLM:** Véc-tơ đặc trưng phổ 57 chiều được sử dụng làm tín hiệu điều kiện (conditioning signal) để điều biến véc-tơ biểu diễn chu kỳ đã tổng hợp, thông qua mạng Feature-wise Linear Modulation (FiLM) [CITE: Perez et al. 2018]. Một mạng MLP hai tầng nội suy cặp hệ số (γ, β) và biến đổi biểu diễn h theo công thức:

h ← (σ(γ) + 0.5) ⊙ h + β

trong đó σ là hàm sigmoid; số hạng σ(γ) + 0.5 giữ hệ số tỉ lệ dao động quanh 1.0 nhằm ổn định quá trình huấn luyện. Cơ sở lý thuyết của thiết kế này là sự cộng hưởng thông tin: chuỗi dữ liệu thô cung cấp "hình dạng" động học của chu kỳ phóng hiện tại, trong khi đặc trưng phổ đại diện cho "chữ ký tần số" của mức độ suy thoái tổng thể. Việc điều biến được thực hiện sau bước gộp token — chữ ký suy thoái toàn cục hiệu chỉnh trực tiếp biểu diễn cô đọng của chu kỳ trước khi đưa vào tầng dự đoán.

**Đầu hồi quy dự đoán:** Véc-tơ đặc trưng sau điều biến được truyền qua một đầu hồi quy hai tầng (kích thước 64 → 32 → 1, sử dụng hàm kích hoạt GELU và tỷ lệ Dropout 0.3) để xuất ra giá trị SOH liên tục.

## 3.4. Thiết lập quá trình huấn luyện

Quy trình tối ưu hóa mô hình được thiết kế với các tham số và chiến lược sau:

- **Hàm mục tiêu:** Sử dụng hàm SmoothL1 (với hệ số β = 0.02). Hàm này chuyển sang chế độ tuyến tính đối với các phần dư vượt ngưỡng 2% SOH, hạn chế ảnh hưởng của gradient lớn và duy trì sự ổn định của quá trình cập nhật trọng số trước nhiễu của nhãn dữ liệu. Đồng thời, hàm mất mát được tinh chỉnh nhân đôi trọng số phạt đối với các dải quan sát cận ngưỡng hết vòng đời (SOH < 80%), nhằm giảm thiểu rủi ro vận hành sinh ra từ sai số dự đoán ở giai đoạn nghiêm trọng này.
- **Thuật toán tối ưu:** AdamW (hệ số weight decay = 3×10⁻⁴) kết hợp cùng lịch trình tinh chỉnh tốc độ học CosineAnnealingWarmRestarts (T₀ = 80 tại pha huấn luyện cuối; T₀ = 3 trong các pha khởi động). Chính quy hóa bổ sung gồm Dropout 0.3 và nhiễu Gaussian biên độ 0.0075 trên chuỗi đầu vào đã chuẩn hóa (jitter augmentation).
- **Khởi động độ dài tiệm tiến (Progressive length warmup):** Chiều dài chuỗi đầu vào được gia tăng theo từng pha huấn luyện (256 → 512 → 1024 → 2048 → 4096). Kỹ thuật này giúp không gian biểu diễn của mô hình hội tụ trên các chuỗi ngắn mang tính cục bộ trước khi mở rộng ra khả năng nắm bắt phụ thuộc dài hạn.
- **Cấu hình mô hình tinh gọn (Compact setup):** Được tối ưu hóa riêng biệt sử dụng thuật toán Adam (tốc độ học 5×10⁻⁴, batch size = 32, giới hạn 100 epoch với cơ chế early stopping kiên nhẫn 15 epoch).

## 3.5. Định lượng độ bất định và phát hiện bất thường

**Định lượng bất định (Uncertainty Quantification):** Nhằm tăng cường độ tin cậy cho bài toán dự báo, thay vì xuất ra một giá trị điểm (point estimate), kiến trúc thực thi cơ chế dự báo ngẫu nhiên thông qua 10 lượt suy diễn có áp dụng Dropout (phương pháp Monte Carlo Dropout [CITE: Gal & Ghahramani 2016]), được gộp thành một lượt forward theo batch để tối ưu độ trễ. Giá trị SOH cuối cùng là trung bình cộng của 10 lượt tính toán, trong khi độ lệch chuẩn đóng vai trò định lượng mức độ bất định (epistemic uncertainty) và được ánh xạ thành chỉ số tin cậy chuẩn hóa trong khoảng [0, 1]. Do cấu hình tinh gọn chỉ chứa xấp xỉ 79 nghìn tham số, chi phí tính toán cho 10 lượt forward propagation vẫn hoàn toàn thỏa mãn các rào cản thời gian thực (real-time constraints) trong ứng dụng biên.

**Phát hiện bất thường và Quản lý rủi ro (Anomaly Detection):** Hệ thống tích hợp một mô-đun phát hiện bất thường dựa trên thuật toán Isolation Forest [CITE: Liu et al. 2008] (cấu hình: 100 cây ước lượng, hệ số contamination = 0.1, random seed = 42). Để tối ưu hóa tài nguyên tính toán, mô-đun này được khớp (fit) trực tiếp lên không gian đặc trưng phổ 57 chiều đã được trích xuất, bỏ qua việc thiết lập một pipeline dư thừa; việc khớp chỉ thực hiện duy nhất trên tập huấn luyện và không lặp lại trong giai đoạn suy diễn, nhằm loại trừ rò rỉ dữ liệu.

Trong giai đoạn suy diễn, giá trị decision_function được sử dụng để phân loại ngưỡng hệ thống thành ba trạng thái động học: Bình thường (Normal), Cảnh báo (Warning tại ngưỡng −0.1) và Bất thường (Anomaly tại ngưỡng −0.3). Cơ chế này hoạt động trực giao (orthogonal) với bốn mức độ suy thoái dài hạn được phân tích từ chỉ số SOH: Khỏe mạnh (Healthy ≥ 90%), Đang suy thoái (Degrading ≥ 85%), Cần bảo trì (Maintenance Required ≥ 80%), và Kết thúc vòng đời (End of Life < 80% — căn cứ theo quy ước kỹ thuật của NASA cho dòng cell 18650 [CITE]).

Hai trục phân tích độc lập (Suy thoái SOH dài hạn và Bất thường động học ngắn hạn), kết hợp cùng các tham số an toàn phần cứng cốt lõi (ngưỡng điện áp, nhiệt độ, dòng điện tuyệt đối), được tổng hợp thông qua một ma trận luật logic (rule-based matrix), xuất ra bốn mức rủi ro (Low, Medium, High, Critical) và ánh xạ sang ba mức ưu tiên bảo trì tương ứng (P1/P2/P3). Thiết kế phân tách trục đánh giá này nhằm đảm bảo tính toàn vẹn của hệ thống: thuật toán học sâu chịu trách nhiệm ước lượng xu hướng suy thoái dài hạn; mô hình thống kê Isolation Forest phụ trách nhận diện các nhiễu loạn cảm biến ngẫu nhiên; trong khi các ranh giới an toàn vật lý đóng vai trò chốt chặn cuối cùng (hard constraints) mà trí tuệ nhân tạo không được phép ghi đè.

---

## DANH SÁCH SỬA so với bản Docs của user (17/07 — KHÔNG copy phần này vào Docs)

| # | Mục | Sửa gì | Căn cứ |
|---|-----|--------|--------|
| 1 | 3.1 | Công thức SOH viết lại dạng text sạch; sửa typo "nomimal" → "nominal" | — |
| 2 | 3.1 | Bỏ dòng "(Hình F5...)" — bộ hình chốt chỉ còn 3 hình (F7/F1/F2), F5 đã bỏ. Thay bằng đoạn giới thiệu LOBO (trước đây thiếu — Table 2 §4.3 cần được protocol §3.1 giới thiệu trước) | Quyết định bộ hình 16/07 |
| 3 | 3.2 | **"Mặt nạ pha (Phase mask)" → "Tiến độ xả (Discharge progress)"** — kênh 6 thật sự là discharge progress | `preprocess_long.py:72-76` (verify 12/07) |
| 4 | 3.2 | "được nội suy từ tín hiệu gốc" → "được tính toán từ tín hiệu gốc" (derived, không phải interpolated) | `extractor.py` |
| 5 | 3.2 | Cross-ref "Mục 3.5" → "Mục 3.4" (compact setup nằm ở 3.4, không phải 3.5) | cấu trúc bài |
| 6 | 3.2 | Thêm câu compact dùng bộ 6 kênh RIÊNG (V,I,T,t + cycle index + SOC) | `config.py` FEATURES |
| 7 | 3.2 | Thêm câu dẫn Hình 1 (F7) | bộ hình chốt |
| 8 | 3.3 | Bỏ "(Hình F3...)" — F3 đã quyết định bỏ từ trước; chỉ còn Hình 2 (kiến trúc) | Quyết định 13/07 |
| 9 | 3.3 | Điền hệ số mở rộng E = 2; viết công thức SSM + Ā = exp(Δ_t·A) dạng text | `soh_predictor.py` |
| 10 | 3.3 | **"P16S16 → 256 token" → "patch 16, stride 8 (chồng lấp 50%) → 511 token"** — P16S16/256 là config v2.0 cũ, checkpoint v2.2 dùng stride 8 | checkpoint metadata `patch_stride: 8`; công thức (4096−16)/8+1=511 verified `soh_predictor.py:379` |
| 11 | 3.3 | Thêm đoạn PatchDegradationEncoder (bản Docs thiếu hẳn khối này) | `soh_predictor.py:225` |
| 12 | 3.3 | **Đảo thứ tự: Attention Pooling TRƯỚC FiLM** (bản Docs viết FiLM điều biến chuỗi trước khi gộp — sai với forward()); công thức FiLM đúng: h ← (σ(γ)+0.5)⊙h+β | `soh_predictor.py:431-477` (verify 12/07) |
| 13 | 3.3 | **"Attention Pooling đa đầu / mỗi đầu chú ý..." → 1 đầu** — checkpoint v2.2 dùng attention_heads=1; multi-head (GH-37) là option không dùng trong model headline | checkpoint `attention_heads: 1` |
| 14 | 3.3 | Dropout đầu hồi quy 0.2 → **0.3** (0.2 là config window-30 rules; long v2.2 dùng 0.3) | checkpoint `dropout: 0.3` |
| 15 | 3.4 | Điền β = 0.02; sửa mô tả "cắt gradient" → "chuyển chế độ tuyến tính" (đúng bản chất SmoothL1) | checkpoint `loss: smooth_l1_beta0.02` |
| 16 | 3.4 | Điền weight decay = 3×10⁻⁴; **T₀ = 80** (không phải 25 như plan cũ) + T₀ = 3 pha warmup; thêm Dropout 0.3 + jitter 0.0075 | checkpoint metadata |
| 17 | 3.4 | Compact: điền lr = 5×10⁻⁴ (xác nhận Adam, batch 32, ≤100 epoch, patience 15 — bản Docs đúng) | `train.py:82-85,294` (verify 17/07) |
| 18 | 3.4 | Bỏ [TODO bảng siêu tham số phụ lục] — số đã điền đủ trong văn; phụ lục đã quyết không làm | Quyết định appendix 12/07 |
| 19 | 3.5 | **"20 lượt" → "10 lượt"** (2 chỗ) + thêm "gộp batch" | `inference.py:212 MC_RUNS=10` (GH-63) |
| 20 | 3.5 | **"66 nghìn" → "79 nghìn"** tham số | đếm params 79,467 (07/07) |
| 21 | 3.5 | Thêm câu "khớp duy nhất trên tập huấn luyện, không lặp lại khi suy diễn" | chống câu hỏi leakage |
| 22 | 3.5 | "4 phân cấp rủi ro tương ứng P1/P2/P3" → "bốn mức rủi ro (Low/Medium/High/Critical) ánh xạ sang ba mức ưu tiên (P1/P2/P3)" | `anomaly_detector.py:141-150` (verify 17/07) |
