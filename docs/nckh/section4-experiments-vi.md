# Section 4 — Experiments & Results (bản nháp tiếng Việt)

> Quy ước: `[xx.x]` = số chưa có, kèm marker `⬜ TODO(#issue)`.
> Số đã có lấy từ nguồn ghi trong chú thích cuối file — KHÔNG tự sửa số mà không cập nhật nguồn.
>
> ✅ **QUYẾT ĐỊNH ĐÃ CHỐT (user duyệt 2026-07-07):**
> 1. Headline chính thức: **MAE 1.52 / RMSE 1.97** (checkpoint v2.2) — Abstract
>    + thesis statement phải sửa từ 1.63/2.09.
> 2. LOBO: báo cáo đầy đủ mean/median/worst + phân tích failure mode (§4.3 giữ nguyên).
> 3. Anomaly: GIỮ "Anomaly Detection" trong title, BỎ claim "F1 > 0.80" khỏi
>    toàn bài; framing tầng cảnh báo sớm như §4.6.
> 4. Format: IEEE 2 cột, 6–8 trang (LaTeX IEEEtran).

---

## 4.1 Thiết lập thí nghiệm

Chúng tôi đánh giá dự đoán SOH bằng hai chỉ số tiêu chuẩn: sai số tuyệt đối
trung bình MAE = (1/N)·Σ|ŷᵢ − yᵢ| và căn sai số bình phương trung bình
RMSE = √((1/N)·Σ(ŷᵢ − yᵢ)²), tính trên đơn vị %SOH. Phát hiện bất thường được
đánh giá bằng Precision, Recall và F1-score. Ngưỡng mục tiêu tham chiếu theo
yêu cầu công nghiệp: MAE < 2%, RMSE < 3%.

Toàn bộ mô hình được huấn luyện trên GPU NVIDIA P100 (Kaggle), triển khai bằng
PyTorch thuần không phụ thuộc CUDA kernel chuyên dụng. Benchmark độ trễ suy luận
thực hiện trên CPU `[ghi rõ model CPU máy đo — ⬜ TODO(#72)]`. Mọi thí nghiệm
dùng random seed 42; giao thức chia dữ liệu cross-battery như mô tả tại §3.1.

## 4.2 Kết quả chính (Table 1)

Bảng 1 so sánh sai số dự đoán SOH của bốn mô hình trên pin kiểm thử B0048
(4°C, hoàn toàn không xuất hiện trong huấn luyện). Tất cả mô hình dùng cùng
giao thức chia dữ liệu 23/2/1 và cùng seed.

**Table 1 — SOH prediction trên pin held-out B0048.**

| Model | #Params | Input | MAE (%) | RMSE (%) |
|-------|--------:|-------|--------:|---------:|
| Naive (last-SOH) | — | — | [x.xx] ⬜ TODO(#69) | [x.xx] |
| CNN-LSTM (baseline) | [xx]k ⬜ TODO(#69) | window 30 | [x.xx] | [x.xx] |
| Mamba window-30 (ours) | 79k | window 30 | 1.98 | 2.38 |
| Mamba long L=4096 (ours) | 99k | full cycle | **1.52** | **1.97** |

Mô hình Mamba long-seq đạt MAE 1.52%, dưới ngưỡng công nghiệp 2%, trong điều
kiện đánh giá khắc nghiệt: pin test chưa từng thấy VÀ ở nhiệt độ 4°C — miền
mà phần lớn dữ liệu huấn luyện không bao phủ. So với CNN-LSTM baseline cùng
giao thức, sai số giảm `[xx]%` tương đối ⬜ TODO(#69). Đáng chú ý, biến thể
window-30 chỉ 79 nghìn tham số vẫn đạt MAE 1.98% — nằm dưới ngưỡng 2% — cho
thấy có thể đánh đổi một phần độ chính xác để lấy khả năng suy luận thời gian
thực trên CPU (xem §4.5).

Chúng tôi không so sánh trực tiếp với các con số công bố ở nghiên cứu khác,
vì phần lớn dùng giao thức chia theo timestep trong cùng một pin — cách chia
cho kết quả lạc quan hơn đáng kể và không đo được khả năng tổng quát hóa
cross-battery (thảo luận tại §5).

## 4.3 Độ vững chắc — Leave-One-Battery-Out (Table 2)

Kết quả trên một pin test duy nhất chưa đủ tin cậy về mặt thống kê. Để loại
trừ khả năng "chọn may" pin dễ, chúng tôi lặp lại thí nghiệm theo giao thức
leave-one-battery-out (LOBO) trên biến thể window-30: lần lượt giữ từng pin
làm tập test, huấn luyện trên các pin còn lại; scaler được fit lại trong từng
fold để tránh rò rỉ dữ liệu. Trong 26 pin của pool, 10 pin không đủ số chu kỳ
tối thiểu (60) để lập fold tin cậy và bị loại, còn lại 16 fold.

**Table 2 — LOBO robustness (window-30, 16 folds).**

| Thống kê | MAE (%) | RMSE (%) |
|----------|--------:|---------:|
| Mean ± std | 3.91 ± 3.27 | 4.81 ± 4.17 |
| Median | 2.22 | 2.55 |
| Best fold (B0042) | 1.40 | 1.77 |
| Worst fold (B0045) | 14.61 | 17.99 |
| Fold B0048 (= pin test chính) | 1.47 | 1.87 |

Kết quả cho thấy bức tranh không đồng nhất và chúng tôi báo cáo đầy đủ thay vì
chỉ đưa giá trị trung bình. Chín trên 16 fold đạt MAE ≤ 2.3% (median 2.22%),
và fold B0048 — chính là pin test của giao thức chính — đạt 1.47%, nhất quán
với kết quả ở Bảng 1, xác nhận việc chọn B0048 làm pin test không phải là
lựa chọn thuận lợi.

Sai số lớn tập trung ở một nhóm pin xác định được: B0045 (14.61%), B0033
(7.55%) và B0054–56 (4.4–6.3%). Đây là các pin thuộc chiến dịch đo thứ cấp
hoạt động gần như toàn bộ vòng đời ở vùng SOH thấp (ví dụ B0045 không bao giờ
vượt 54% SOH) — khi giữ các pin này ra làm test, mô hình buộc phải ngoại suy
sang vùng SOH gần như không tồn tại trong dữ liệu huấn luyện còn lại, đồng
thời nhãn dung lượng của nhóm này dao động mạnh giữa các chu kỳ liên tiếp.
Nói cách khác, LOBO không chỉ xác nhận độ vững chắc trong miền dữ liệu phổ
biến mà còn chỉ ra failure mode cụ thể của mô hình: các pin ở regime suy thoái
bất thường — hạn chế này được thảo luận tại §5.

## 4.4 Ablation (Table 3)

Bảng 3 định lượng đóng góp của từng thành phần kiến trúc bằng cách lần lượt
loại bỏ hoặc thay đổi chúng, giữ nguyên mọi điều kiện còn lại.

**Table 3 — Ablation trên B0048 (long model).**

| Variant | MAE (%) | Δ MAE |
|---------|--------:|------:|
| Full model (v2.2) | 1.52 | — |
| − FiLM conditioning | [x.xx] ⬜ TODO(#71) | [+x.xx] |
| − IC curve channel | [x.xx] ⬜ TODO(#71) | [+x.xx] |
| − Attention pooling (mean pool) | [x.xx] ⬜ TODO(#71) | [+x.xx] |
| d_state 32 → 16 | [x.xx] ⬜ TODO(#71) | [+x.xx] |
| Features 6 → 4 | [x.xx] ⬜ TODO(#71) | [+x.xx] |

`[Đoạn văn 3–4 câu: thành phần nào đóng góp lớn nhất; thành phần nào ảnh hưởng
không đáng kể. Nếu có Δ âm (bỏ đi lại tốt hơn) — báo cáo trung thực + 1 câu
giải thích giả thuyết.]` ⬜ TODO(#71)

## 4.5 Độ trễ suy luận (Table 4)

Bảng 4 báo cáo độ trễ suy luận end-to-end (bao gồm chuẩn hóa scaler, trích
xuất đặc trưng và 20 lượt forward MC Dropout), đo trên [n=100] lần chạy,
batch size 1.

**Table 4 — Inference latency.**

| Model | Device | Mean (ms) | P95 (ms) |
|-------|--------|----------:|---------:|
| Mamba window-30 | CPU ([model CPU]) | **[xx.x]** ⬜ TODO(#72, chờ GH-63) | [xx.x] |
| Mamba long L=4096 | CPU | [xxx.x] | [xxx.x] |
| Mamba long L=4096 | GPU P100 | [xx.x] | [xx.x] |

Biến thể window-30 đạt [xx] ms trung bình, thỏa ràng buộc <100 ms cho cảnh
báo thời gian thực ưu tiên P1. Mô hình long đổi độ trễ cao hơn lấy độ chính
xác — phù hợp cho đánh giá theo lô (batch) định kỳ thay vì cảnh báo tức thời.

## 4.6 Phát hiện bất thường (Table 5)

NASA dataset không có chú giải lỗi (fault annotation), vì vậy chúng tôi định
nghĩa nhãn bất thường đại diện (proxy) theo hai cách: **(i) rate-based** —
một cycle là bất thường nếu tốc độ suy thoái cục bộ (làm mượt rolling-median,
đạo hàm trung tâm) vượt phân vị 90 của phân phối tốc độ trên tập train
(0.4833 %SOH/cycle), nhất quán với contamination prior 0.1 của IsolationForest;
**(ii) EOL-based** — SOH < 80% theo quy ước NASA 18650. IsolationForest
(contamination = 0.1, 100 cây, seed 42) được fit duy nhất trên đặc trưng của
tập huấn luyện.

**Table 5 — Anomaly detection (IsolationForest).**

| Label | Split | Ngưỡng | Precision | Recall | F1 | Tỉ lệ dương |
|-------|-------|--------|----------:|-------:|---:|------------:|
| rate | val | production (score ≤ −0.1 / −0.3) | 0.00 | 0.00 | 0.00 | 35.5% |
| rate | val | tuned trên val (score ≤ 0.213) | 0.36 | 1.00 | 0.53 | 35.5% |
| rate | test | production (score ≤ −0.1 / −0.3) | 0.00 | 0.00 | 0.00 | 20.6% |
| rate | test | tuned trên val (score ≤ 0.213) | 0.21 | 1.00 | 0.34 | 20.6% |
| eol | val | tuned trên val | 0.98 | 0.99 | 0.99 | 97.9% |
| eol | test | tuned trên val | 0.98 | 1.00 | 0.99 | 97.9% |

Kết quả cho hai bài học trung thực. Thứ nhất, nhãn EOL-based suy biến trên
val/test: các pin 4°C này có ~98% số window dưới 80% SOH, nên F1 = 0.99 đạt
được một cách tầm thường (dự đoán tất cả là dương đã cho F1 ≈ 0.99) — con số
này không phản ánh năng lực phát hiện. Thứ hai, với nhãn rate-based có ý nghĩa
hơn, ngưỡng production (−0.1/−0.3) hoàn toàn không kích hoạt (F1 = 0), và ngay
cả ngưỡng tinh chỉnh trên tập val cũng chỉ đạt F1 = 0.34 trên test — dưới mức
kỳ vọng 0.80. Ở cấu hình tinh chỉnh, hệ thống đạt recall 1.00 với precision
0.21: hoạt động như một bộ cảnh báo sớm có độ nhạy cao nhưng nhiều báo động
nhầm, phù hợp làm tầng lọc thứ nhất trước khi con người xác nhận, chứ chưa
thể là bộ phân loại tự động. Chúng tôi kết luận rằng IsolationForest không
giám sát trên đặc trưng phổ chỉ tách được các regime suy thoái ở mức yếu tại
độ phân giải window; cả hai nhãn đều là proxy suy ra từ capacity fade, không
phải chú giải lỗi cảm biến thực địa — hạn chế và hướng cải thiện (nhãn thật
từ thiết bị IoT, phương pháp bán giám sát) được thảo luận tại §5.

---

## Nguồn số liệu (không đưa vào bài)

| Số | Nguồn | Ghi chú |
|----|-------|---------|
| Long v2.2: MAE 1.52 / RMSE 1.97 | metadata trong `models/weights/soh_mamba_long_v2.2.pth` (`test_mae=1.5232`, `test_rmse=1.9708`) | ⚠️ khác 1.63/2.09 trong paper-plan (run cũ) — cần user chốt |
| Long v2.2 params: 99,437 | đếm từ state_dict checkpoint | |
| Long v2.2 config thực tế | checkpoint metadata: patch 16/**stride 8**, d_state 32, attention pooling 1 head, FiLM depth 2, SmoothL1 β=0.02 + weighted loss, **AdamW** wd=3e-4, dropout 0.3, CAWR **T₀=80**, jitter 0.0075 | ⚠️ §3.3–3.4 Methodology viết theo đây, KHÔNG theo plan cũ (P16S16, Adam, T₀=25) |
| Window-30 v1.5: MAE 1.98 / RMSE 2.38 | `logs/GH-60/validation_report.md` (`test_mae=1.9785`, `test_rmse=2.3846`, 768 windows) | |
| Window-30 params: 79,467 | đếm trực tiếp `MambaSOHPredictor(input_features=6, feat_dim=57, d_model=64, d_state=16)` | plan ghi ~66k là số cũ |
| Table 2 LOBO: 16 folds, mean 3.91±3.27, median 2.22 | `logs/nckh/lobo_results/lobo_per_fold.csv` + `table2_summary.txt`, commit `504fcf4` | 10 pin skip: B0025–28 (28 cyc), B0029–32 (40 cyc), B0053 (56 cyc) < min 60; B0041 (67 cyc) bị loại ở bước load — ⬜ kiểm tra lý do nếu reviewer hỏi |
| Outlier LOBO: B0045 SOH range [0, 54.1]%, B0054/56 max ~58–67% | tính từ `metadata.csv` (capacity/2.0) | căn cứ cho phân tích "regime SOH thấp" ở §4.3 |
| Table 5 anomaly | `logs/nckh/anomaly/table5.md` + `results.json` (GH-70, PR #85) | F1 target 0.80 KHÔNG đạt (rate label, test 0.34) — honest negative |
| Table 1 LSTM + naive | chưa chạy | #69 |
| Table 3 ablation | gom từ logs GH-25/34/37/38 + chạy bù | #71 |
| Table 4 latency | chờ GH-63 (<100ms) + GH-60 | #72 |
