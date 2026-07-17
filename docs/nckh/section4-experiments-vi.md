# Section 4 — Experiments & Results (bản COPY-READY cho Google Docs)

> Cập nhật 17/07: chuyển thành bản copy-paste sạch (như section3). Copy từ
> mục 4.1 đến hết 4.6; KHÔNG copy phần "Nguồn số liệu" và ghi chú cuối file.
> Công thức viết dạng text; bôi đậm trong bảng cần làm lại thủ công trong
> Docs (paste thường rớt format): Table 1 đậm 1.52/1.97; Table 3 đậm +0.41;
> Table 3b đậm −4.57; Table 4 đậm 56.1/78.3.
> Hình duy nhất của section này: HÌNH 3 — chèn sau đoạn phân tích Bảng 1
> (đã có câu dẫn trong văn), caption dán dưới ảnh:
> "Fig. 3. Predicted vs. ground-truth SOH on the held-out test battery
> B0048 (shaded: ±1 std, MC Dropout)."

---

## 4.1 Thiết lập thí nghiệm

Chúng tôi đánh giá dự đoán SOH bằng hai chỉ số tiêu chuẩn: sai số tuyệt đối trung bình MAE = (1/N)·Σ|ŷᵢ − yᵢ| và căn sai số bình phương trung bình RMSE = √((1/N)·Σ(ŷᵢ − yᵢ)²), tính trên đơn vị %SOH. Phát hiện bất thường được đánh giá bằng Precision, Recall và F1-score. Ngưỡng mục tiêu tham chiếu theo yêu cầu công nghiệp: MAE < 2%, RMSE < 3%.

Toàn bộ mô hình được huấn luyện trên GPU Kaggle, triển khai bằng PyTorch thuần không phụ thuộc CUDA kernel chuyên dụng. Benchmark độ trễ suy luận thực hiện trên CPU Intel Core i7-14650HX. Mọi thí nghiệm dùng random seed 42; giao thức chia dữ liệu cross-battery như mô tả tại Mục 3.1.

## 4.2 Kết quả chính

Bảng 1 so sánh sai số dự đoán SOH của bốn mô hình trên pin kiểm thử B0048 (4°C, hoàn toàn không xuất hiện trong huấn luyện). Tất cả mô hình dùng cùng giao thức chia dữ liệu 23/2/1 và cùng seed.

Table 1 — SOH prediction trên pin held-out B0048 (split 23/2/1).

| Model | #Params | Input | MAE (%) | RMSE (%) |
|-------|--------:|-------|--------:|---------:|
| Naive last-SOH (oracle)† | — | SOH thật của cycle trước | 0.89 | 1.49 |
| CNN-LSTM (baseline) | 61k | telemetry window 30 | 4.90 | 6.49 |
| Mamba window-30 (ours) | 79k | telemetry window 30 | 1.98 | 2.38 |
| Mamba long L=4096 (ours) | 99k | telemetry full cycle | **1.52** | **1.97** |

† Oracle baseline — cần giá trị SOH thật (đo dung lượng) của chu kỳ liền trước, thông tin KHÔNG tồn tại khi triển khai thực tế; xem thảo luận dưới.

Trong nhóm mô hình chỉ dùng telemetry thô — điều kiện triển khai thực tế — Mamba long-seq đạt MAE 1.52%, dưới ngưỡng công nghiệp 2%, giảm 69% sai số tương đối so với CNN-LSTM cùng giao thức (4.90%); biến thể window-30 giảm 60% (1.98%). Kết quả đạt được trong điều kiện đánh giá khắc nghiệt: pin test chưa từng thấy VÀ ở nhiệt độ 4°C — miền mà phần lớn dữ liệu huấn luyện không bao phủ. CNN-LSTM với cửa sổ 30 bước tỏ ra không đủ sức tổng quát hóa cross-battery, củng cố lựa chọn kiến trúc SSM. Hình 3 đối chiếu quỹ đạo SOH dự đoán với giá trị thật trên pin kiểm thử, kèm dải bất định MC Dropout.

*(→ CHÈN HÌNH 3 TẠI ĐÂY, caption: Fig. 3. Predicted vs. ground-truth SOH on the held-out test battery B0048 (shaded: ±1 std, MC Dropout).)*

Baseline naive (SOH chu kỳ này = SOH đo được của chu kỳ trước) đạt MAE 0.89% — tốt hơn mọi mô hình học máy. Chúng tôi báo cáo trung thực con số này và lưu ý nó KHÔNG phải phương pháp cạnh tranh: naive đòi hỏi biết SOH thật của chu kỳ liền trước, tức phải đo dung lượng bằng chu trình xả kiểm soát — chính là phép đo mà hệ thống giám sát thực địa không thể thực hiện mỗi chu kỳ. Giá trị của nó là một "trần tham chiếu" (oracle): SOH biến thiên chậm giữa các chu kỳ liên tiếp, nên bài toán có ý nghĩa duy nhất là ước lượng SOH từ telemetry khi KHÔNG có lịch sử dung lượng — đúng nhiệm vụ mà các mô hình trong bảng giải quyết.

Chúng tôi không so sánh trực tiếp với các con số công bố ở nghiên cứu khác, vì phần lớn dùng giao thức chia theo timestep trong cùng một pin — cách chia cho kết quả lạc quan hơn đáng kể và không đo được khả năng tổng quát hóa cross-battery (thảo luận tại Mục 5).

Cải thiện data-centric. Phân tích lỗi theo dải SOH (Mục 4.4) cho thấy biến thể window-30 bias âm hệ thống ở vùng SOH cao của miền 4°C — vùng mà các pin 4°C trong tập huấn luyện cũ chỉ phủ tới 67.2% SOH. Bổ sung một pin 4°C phủ vùng SOH cao vào tập huấn luyện (B0047, SOH 0–83.7%) — không đổi kiến trúc, không đổi siêu tham số — giảm MAE window-30 từ 1.98% xuống 1.34% (RMSE 2.38% → 1.84%) trên cùng pin test B0048. Kết quả này báo cáo tách khỏi Bảng 1 vì tập huấn luyện khác (24 pin, split 24/1/1); nó minh họa rằng trong bài toán cross-domain, độ phủ của dữ liệu huấn luyện quan trọng ngang lựa chọn kiến trúc.

## 4.3 Độ vững chắc — Leave-One-Battery-Out

Kết quả trên một pin test duy nhất chưa đủ tin cậy về mặt thống kê. Để loại trừ khả năng "chọn may" pin dễ, chúng tôi lặp lại thí nghiệm theo giao thức leave-one-battery-out (LOBO) trên biến thể window-30: lần lượt giữ từng pin làm tập test, huấn luyện trên các pin còn lại; scaler được fit lại trong từng fold để tránh rò rỉ dữ liệu. Trong 26 pin của pool, 10 pin không đủ số chu kỳ tối thiểu (60) để lập fold tin cậy và bị loại, còn lại 16 fold.

Table 2 — LOBO robustness (window-30, 16 folds).

| Thống kê | MAE (%) | RMSE (%) |
|----------|--------:|---------:|
| Mean ± std | 3.91 ± 3.27 | 4.81 ± 4.17 |
| Median | 2.22 | 2.55 |
| Best fold (B0042) | 1.40 | 1.77 |
| Worst fold (B0045) | 14.61 | 17.99 |
| Fold B0048 (= pin test chính) | 1.47 | 1.87 |

Kết quả cho thấy bức tranh không đồng nhất và chúng tôi báo cáo đầy đủ thay vì chỉ đưa giá trị trung bình. Chín trên 16 fold đạt MAE ≤ 2.3% (median 2.22%), và fold B0048 — chính là pin test của giao thức chính — đạt 1.47%, nhất quán với kết quả ở Bảng 1, xác nhận việc chọn B0048 làm pin test không phải là lựa chọn thuận lợi.

Sai số lớn tập trung ở một nhóm pin xác định được: B0045 (14.61%), B0033 (7.55%) và B0054–56 (4.4–6.3%). Đây là các pin thuộc chiến dịch đo thứ cấp hoạt động gần như toàn bộ vòng đời ở vùng SOH thấp (ví dụ B0045 không bao giờ vượt 54% SOH) — khi giữ các pin này ra làm test, mô hình buộc phải ngoại suy sang vùng SOH gần như không tồn tại trong dữ liệu huấn luyện còn lại, đồng thời nhãn dung lượng của nhóm này dao động mạnh giữa các chu kỳ liên tiếp. Nói cách khác, LOBO không chỉ xác nhận độ vững chắc trong miền dữ liệu phổ biến mà còn chỉ ra failure mode cụ thể của mô hình: các pin ở regime suy thoái bất thường — hạn chế này được thảo luận tại Mục 5.

## 4.4 Ablation & phân tích lỗi

(a) Ablation thành phần. Bảng 3 định lượng đóng góp của các thành phần có thể tách rời bằng cách huấn luyện lại mô hình long với từng thay đổi, giữ nguyên mọi điều kiện còn lại.

Table 3 — Component ablation trên B0048 (long model, split 23/2/1).

| Variant | MAE (%) | RMSE (%) | Δ MAE |
|---------|--------:|---------:|------:|
| Full model | 1.52 | 1.97 | — |
| Attention pooling → last token | 1.93 | 2.38 | **+0.41** |
| d_state 32 → 16 | 1.24 | 1.61 | −0.28 |
| Bỏ EOL-weighted loss | 1.32 | 1.69 | −0.20 |

Attention pooling đóng góp rõ rệt: thay bằng lấy token cuối (last-token pooling) làm MAE tăng từ 1.52% lên 1.93% (+0.41 điểm phần trăm, +27% tương đối) — phù hợp trực giác rằng với chuỗi 511 token sau patch encoding, tín hiệu suy thoái không tập trung ở token cuối mà phân tán khắp chuỗi, nên cơ chế attention tổng hợp toàn cục có lợi thế rõ so với chỉ lấy trạng thái ẩn cuối cùng. Đây là thành phần kiến trúc duy nhất trong ba biến thể có đóng góp dương, và cũng là thành phần gắn trực tiếp với contribution claim về kiến trúc (Mục 1).

Hai biến thể còn lại đều cho Δ MAE âm — giảm d_state từ 32 xuống 16 (−0.28) và bỏ EOL-weighted loss (−0.20) đều làm MAE trên B0048 tốt hơn cả full model. Chúng tôi báo cáo trung thực cả hai thay vì loại bỏ, và diễn giải theo cùng một logic: B0048 là một pin test duy nhất với SOH trải rộng 0–83.7% nhưng đa số cycle nằm ngoài vùng gần EOL, nên (i) trạng thái ẩn lớn hơn (d_state=32) có thể đang overfit vào các đặc điểm riêng của tập 26 pin huấn luyện thay vì giúp tổng quát hóa, và (ii) việc nhân đôi trọng số cho mẫu SOH < 80% (EOL-weighted loss) tối ưu đúng vùng mà B0048 có ít mẫu nhất, nên cải thiện ở vùng đó không đủ bù cho chi phí ở phần còn lại của đường cong. Bằng chứng LOBO (Mục 4.3, 16 fold, std 3.27%) đã cho thấy hiệu năng dao động đáng kể giữa các pin; hai Δ âm ở đây khả năng cao phản ánh cùng nguồn phương sai đó hơn là bằng chứng chắc chắn rằng d_state=16 hoặc bỏ weighted-loss tốt hơn nói chung — kết luận đó cần LOBO trên chính các biến thể này để xác nhận, việc chúng tôi để lại cho hướng phát triển tiếp theo (Mục 5.5) do giới hạn thời gian và ngân sách tính toán. Diễn giải overfitting ở trên nhất quán với một quan sát độc lập trên cùng họ dữ liệu NASA: SambaMixer [CITE: Olalde-Verano et al., IEEE Access 2025] báo cáo hiệu năng giảm khi tăng quy mô model từ 48.7M lên 85.6M tham số, với cùng giả thuyết overfitting trên tập dữ liệu nhỏ (Mục 5.3) — củng cố khả năng rằng giới hạn nằm ở dung lượng dữ liệu chứ không phải lỗi cấu hình riêng của mô hình chúng tôi.

Chúng tôi vẫn giữ d_state=32 và weighted-loss trong mô hình headline vì hai lý do không thuần túy dựa trên MAE của một pin test: d_state lớn hơn là lựa chọn có chủ đích để tăng năng lực mô hình cho chuỗi L=4096; và EOL-weighted loss ưu tiên độ tin cậy tại ngưỡng ra quyết định thay thế pin — nơi sai số có chi phí vận hành cao hơn sai số ở vùng SOH khỏe mạnh — phù hợp mục tiêu ứng dụng bảo trì dự đoán hơn là tối thiểu hóa MAE trung bình thuần túy trên một pin.

(b) Phân tích lỗi theo dải SOH. Để hiểu mô hình sai ở đâu thay vì chỉ sai bao nhiêu, chúng tôi phân rã sai số của biến thể window-30 trên B0048 theo dải SOH (số liệu từ cấu hình đã bổ sung B0047 vào tập huấn luyện, xem đoạn "Cải thiện data-centric" ở Mục 4.2):

Table 3b — Per-band test MAE trên B0048 (window-30, tập huấn luyện mở rộng).

| Dải SOH | n windows | MAE (%) | Bias (%) |
|---------|----------:|--------:|---------:|
| 50–60% | 69 | 1.55 | +0.94 |
| 60–70% | 512 | 1.18 | +0.13 |
| 70–80% | 171 | 1.43 | −0.91 |
| 80–90% | 16 | 4.57 | **−4.57** |

Sai số tập trung gần như hoàn toàn ở dải 80–90%: mô hình dự đoán thấp hơn thực tế một cách hệ thống (bias −4.57%), trong khi ba dải dưới đều đạt MAE ≤ 1.55%. Dải này chỉ gồm 16 window đến từ đúng một giá trị SOH thật (82.9%) của một pin — cỡ mẫu quá nhỏ để kết luận, nhưng hệ quả thực tiễn đáng lưu ý: bias âm quanh ngưỡng EOL 80% có thể khiến pin khỏe bị phân loại nhầm thành hết vòng đời. Trước khi bổ sung B0047, 100% mẫu MC Dropout của các window này nằm dưới 80%; sau bổ sung, 9/16 window đã dự đoán ≥78%. Cải thiện rõ nhưng chưa triệt để — chúng tôi ghi nhận đây là hạn chế mở tại Mục 5.

## 4.5 Độ trễ suy luận

Bảng 4 báo cáo độ trễ suy luận end-to-end qua gRPC (bao gồm chuẩn hóa scaler, trích xuất đặc trưng và 10 mẫu MC Dropout đã gộp batch), đo 50 lần lặp mỗi RPC với real weights trên CPU Intel Core i7-14650HX.

Table 4 — Inference latency (window-30, CPU i7-14650HX, n=50).

| Đường gọi | Mean (ms) | P50 (ms) | P95 (ms) |
|-----------|----------:|---------:|---------:|
| Pipeline trực tiếp (run_inference) | 58.7 | 58.8 | 79.3 |
| gRPC Predict (unary, end-to-end) | **56.1** | 52.5 | **78.3** |
| gRPC PredictStream (per window) | 60.8 | 61.9 | 66.5 |

Biến thể window-30 đạt 56.1 ms trung bình và 78.3 ms P95 end-to-end — thỏa ràng buộc <100 ms cho cảnh báo thời gian thực ưu tiên P1 với biên an toàn ngay cả ở P95. Kết quả đạt được nhờ hai tối ưu: gộp các lượt forward MC Dropout thành một batch duy nhất (494.8 → 124 ms) và giảm số mẫu Monte Carlo từ 20 xuống 10 (124 → ~56–88 ms; độ lệch ước lượng uncertainty thay đổi không đáng kể trên các payload kiểm chứng). Chi phí transport gRPC không đáng kể so với chi phí suy luận (chênh lệch Predict với gọi trực tiếp nằm trong nhiễu đo). Mô hình long đổi độ trễ cao hơn lấy độ chính xác — phù hợp cho đánh giá theo lô (batch) định kỳ thay vì cảnh báo tức thời.

## 4.6 Phát hiện bất thường

NASA dataset không có chú giải lỗi (fault annotation), vì vậy chúng tôi định nghĩa nhãn bất thường đại diện (proxy) theo hai cách: (i) rate-based — một cycle là bất thường nếu tốc độ suy thoái cục bộ (làm mượt rolling-median, đạo hàm trung tâm) vượt phân vị 90 của phân phối tốc độ trên tập train (0.4833 %SOH/cycle), nhất quán với contamination prior 0.1 của Isolation Forest; (ii) EOL-based — SOH < 80% theo quy ước NASA 18650. Isolation Forest (contamination = 0.1, 100 cây, seed 42) được fit duy nhất trên đặc trưng của tập huấn luyện, không fit lại trên dữ liệu đánh giá.

Table 5 — Anomaly detection (Isolation Forest).

| Label | Split | Ngưỡng | Precision | Recall | F1 | Tỉ lệ dương |
|-------|-------|--------|----------:|-------:|---:|------------:|
| rate | val | production (score ≤ −0.1 / −0.3) | 0.00 | 0.00 | 0.00 | 35.5% |
| rate | val | tuned trên val (score ≤ 0.213) | 0.36 | 1.00 | 0.53 | 35.5% |
| rate | test | production (score ≤ −0.1 / −0.3) | 0.00 | 0.00 | 0.00 | 20.6% |
| rate | test | tuned trên val (score ≤ 0.213) | 0.21 | 1.00 | 0.34 | 20.6% |
| eol | val | tuned trên val | 0.98 | 0.99 | 0.99 | 97.9% |
| eol | test | tuned trên val | 0.98 | 1.00 | 0.99 | 97.9% |

Kết quả cho hai bài học trung thực. Thứ nhất, nhãn EOL-based suy biến trên val/test: các pin 4°C này có ~98% số window dưới 80% SOH, nên F1 = 0.99 đạt được một cách tầm thường (dự đoán tất cả là dương đã cho F1 ≈ 0.99) — con số này không phản ánh năng lực phát hiện. Thứ hai, với nhãn rate-based có ý nghĩa hơn, ngưỡng production (−0.1/−0.3) hoàn toàn không kích hoạt (F1 = 0), và ngay cả ngưỡng tinh chỉnh trên tập val cũng chỉ đạt F1 = 0.34 trên test. Ở cấu hình tinh chỉnh, hệ thống đạt recall 1.00 với precision 0.21: hoạt động như một bộ cảnh báo sớm có độ nhạy cao nhưng nhiều báo động nhầm, phù hợp làm tầng lọc thứ nhất trước khi con người xác nhận, chứ chưa thể là bộ phân loại tự động. Chúng tôi kết luận rằng Isolation Forest không giám sát trên đặc trưng phổ chỉ tách được các regime suy thoái ở mức yếu tại độ phân giải window; cả hai nhãn đều là proxy suy ra từ capacity fade, không phải chú giải lỗi cảm biến thực địa — hạn chế và hướng cải thiện (nhãn thật từ thiết bị IoT, phương pháp bán giám sát) được thảo luận tại Mục 5.

---

## Nguồn số liệu (KHÔNG copy vào Docs)

| Số | Nguồn | Ghi chú |
|----|-------|---------|
| Long v2.2: MAE 1.52 / RMSE 1.97, 99,437 params | metadata checkpoint `soh_mamba_long_v2.2.pth` | headline chốt 07/07 |
| Window-30 v1.5: MAE 1.98 / RMSE 2.38, 79,467 params | `logs/GH-60/validation_report.md` | dòng Table 1 (split cũ) |
| v1.6: MAE 1.34 / RMSE 1.84 + per-band Table 3b + case 82.9% | `logs/GH-88/ablation.md` (commit `bcf0aa9`, split MỚI 24/1/1) | §4.2 data-centric + §4.4b |
| Table 2 LOBO: 16 folds, mean 3.91±3.27, median 2.22 | `logs/nckh/lobo_results/` (commit run `504fcf4`) | per-fold CSV đã restore 09/07 |
| Table 5 anomaly | `logs/nckh/anomaly/table5.md` (GH-70, PR #85) | quyết định bỏ claim F1>0.80 |
| Table 1 baselines: CNN-LSTM 4.90/6.49 (61,089 params), naive 0.89/1.49 | `logs/nckh/baseline_results/table1_baselines.json` (Kaggle 09/07, commit `c170e29`) | #69 xong |
| Table 3 ablation 3 variant | `logs/nckh/ablation/*.json` (Kaggle 09–11/07) | #71 xong; bug metadata pooling → issue #100 |
| Table 4 latency | user chạy `benchmark_grpc.py --real-weights` 09/07, i7-14650HX, n=50 | tiến trình 494.8→124→88.2→56.1 |

## Ghi chú thay đổi bản copy-ready 17/07 (KHÔNG copy vào Docs)

1. Công thức MAE/RMSE viết dạng text sạch (bản Docs bị dính đúp: bản vỡ + LaTeX thô).
2. Thêm câu dẫn Hình 3 vào cuối đoạn phân tích Bảng 1 + đánh dấu vị trí chèn ảnh.
3. Khôi phục dấu † ở footnote oracle.
4. Bỏ các tên version nội bộ (v1.5/v1.6/v2.2, GH-34...) khỏi thân bài — Table 3 ghi "Full model", Table 3b ghi "tập huấn luyện mở rộng", đoạn data-centric bỏ "(v1.6)" — người đọc ngoài không biết/không cần biết mã version nội bộ của nhóm; mô tả bằng đặc điểm (bổ sung B0047) thay vì mã.
5. Đổi "§" → "Mục" cho nhất quán với section3; "IsolationForest" → "Isolation Forest" (tên chuẩn có khoảng trắng, khớp §3.5).
6. SambaMixer trong §4.4a thêm [CITE] marker.
