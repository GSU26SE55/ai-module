# Section 3 — Methodology (bản nháp tiếng Việt)

> Mọi thông số trong file này đã verify từ code/checkpoint (nguồn ghi cuối file).
> Chỗ duy nhất còn placeholder: định nghĩa nhãn anomaly §3.5 đã theo quyết định
> 07/07 (rate-based là chính).
> ⚠️ Plan cũ ghi SAI 3 chỗ, file này đã sửa: kênh 6 là **discharge progress**
> (không phải phase mask); patch **stride 8** (không phải 16); optimizer **AdamW**.

---

## 3.1 Dữ liệu và giao thức đánh giá

Chúng tôi sử dụng bộ dữ liệu pin Li-ion 18650 của NASA Ames Prognostics Center
[cite: Saha & Goebel], gồm các chu kỳ sạc–xả đo trong buồng nhiệt độ kiểm soát.
Sau khi loại các pin lỗi dữ liệu (B0036: nhiễu SOH đột biến >120%; B0049–B0052:
chuỗi quá ngắn/hỏng; B0038–B0040: để dự phòng), còn lại 26 pin ở các mức nhiệt
độ môi trường 4°C, 22°C, 24°C và 43°C. SOH của mỗi chu kỳ xả được định nghĩa:

SOH(t) = C(t) / C_nominal × 100%,  với C_nominal = 2.0 Ah.

**Giao thức cross-battery + cross-temperature.** Khác với đa số nghiên cứu chia
train/test theo timestep bên trong cùng một pin, chúng tôi chia HẲN theo battery
ID: 23 pin huấn luyện, 2 pin validation (B0046, B0047 — 4°C) và 1 pin test
(B0048 — 4°C) hoàn toàn tách biệt. Pin test vừa chưa từng xuất hiện trong huấn
luyện, vừa thuộc miền nhiệt độ 4°C ít được bao phủ — buộc mô hình chứng minh
khả năng tổng quát hóa thật thay vì nội suy trong cùng một pin. Tập huấn luyện
có chứa pin 4°C và 43°C để mô hình được quan sát cả hai cực nhiệt độ. Mọi
script dùng random seed 42.

Để đánh giá độ vững chắc thống kê, chúng tôi bổ sung giao thức
leave-one-battery-out (LOBO): lần lượt giữ từng pin làm tập test, huấn luyện
trên các pin còn lại; các scaler được fit lại trong từng fold để tránh rò rỉ
dữ liệu (kết quả tại §4.3).

## 3.2 Đặc trưng đầu vào

**Chuỗi dài (L = 4096).** Mỗi mẫu là toàn bộ telemetry của một chu kỳ xả,
nội suy/cắt về 4096 bước thời gian với 6 kênh: bốn kênh đo trực tiếp
(điện áp V, dòng điện I, nhiệt độ T, thời gian t) và hai kênh dẫn xuất:
(i) đường cong dung lượng gia tăng IC (incremental capacity, dQ/dV) — đặc
trưng kinh điển phản ánh sự dịch chuyển đỉnh điện hóa khi pin lão hóa; và
(ii) tiến độ xả (discharge progress ∈ [0,1]) — tỉ lệ dung lượng đã xả, cung
cấp tín hiệu vị trí trong chu kỳ. Các kênh được chuẩn hóa MinMax [0,1] với
scaler fit riêng trên tập huấn luyện.

**Đặc trưng phổ mức chu kỳ (57 chiều).** Song song với chuỗi thô, mỗi chu kỳ
được tóm tắt bằng vector 57 chiều: 10 đặc trưng phổ (năng lượng theo dải tần,
spectral entropy, hệ số Gini, kurtosis phổ, v.v.) và 9 đặc trưng thống kê,
tính trên 3 kênh V/I/T của TOÀN chu kỳ. Vector này được chuẩn hóa StandardScaler
và đưa vào mô hình qua cơ chế FiLM (§3.3) — cho phép các đặc trưng toàn cục
"điều biến" biểu diễn cục bộ của chuỗi.

**Biến thể window-30.** Cấu hình triển khai thời gian thực dùng cửa sổ 30
bước × 6 đặc trưng (V, I, T, t, chỉ số chu kỳ chuẩn hóa, SOC%) cùng vector
57 chiều tính trên cửa sổ — giữ pipeline đồng nhất giữa huấn luyện và suy luận.

## 3.3 Kiến trúc mô hình

**Nền tảng Mamba (selective SSM).** Khối Mamba ánh xạ chuỗi đầu vào qua mô
hình không gian trạng thái có tham số phụ thuộc đầu vào:

h_t = Ā·h_{t−1} + B̄_t·x_t,        y_t = C_t·h_t,

trong đó Ā = exp(Δ_t·A) với bước rời rạc hóa Δ_t, ma trận B_t, C_t đều được
sinh từ chính x_t (tính "selective" — mô hình tự quyết định giữ/quên thông
tin theo nội dung). Độ phức tạp tuyến tính O(L) theo chiều dài chuỗi, so với
O(L²) của self-attention — yếu tố quyết định ở L = 4096. Mỗi khối gồm:
in-projection (expand ×2) → depthwise Conv1d (k = 4) → SiLU → SSM scan →
out-projection, kèm residual. Chúng tôi cài đặt thuần PyTorch, không phụ
thuộc CUDA kernel chuyên dụng, nên mô hình chạy được trên CPU/Windows —
điều kiện cần cho triển khai biên (edge).

**Mô hình long-seq (99k tham số).** Chuỗi 4096×6 trước tiên qua patch encoder:
mỗi patch 16 bước, stride 8 (chồng lấp 50%), số token L' = (4096−16)/8 + 1 = 511.
Mỗi token được ghép thêm 4 thống kê suy thoái nội-patch (RMS, peak-to-peak,
std, kurtosis) trước khi chiếu về d_model = 64 — tránh nghẽn thông tin khi
nén 8× chuỗi. Tiếp theo là 2 khối Mamba (d_state = 32). Vector phổ 57 chiều
qua MLP 2 tầng sinh cặp (γ, β) điều biến FiLM: h ← γ ⊙ h + β. Cuối cùng,
attention pooling (1 head) tổng hợp 511 token thành biểu diễn chu kỳ, qua
đầu hồi quy dự đoán SOH.

**Biến thể window-30 (79k tham số).** Cùng khung kiến trúc nhưng bỏ patch
encoder (chuỗi 30 bước đủ ngắn), d_state = 16, lấy token cuối thay vì
attention pooling. Đây là mô hình phục vụ suy luận thời gian thực <100 ms
trên CPU (§4.5); ước lượng bất định bằng MC Dropout 20 lượt forward.

*Câu phòng thủ:* (1) Không dùng thư viện `mamba-ssm` CUDA để giữ tính di động
— đã kiểm chứng độ chính xác tương đương. (2) Không so trực tiếp Transformer
cùng protocol vì chi phí O(L²) tại L = 4096 vượt ngân sách tính toán; baseline
so sánh là CNN-LSTM (§4.2) và trích dẫn kết quả Transformer từ văn liệu.

## 3.4 Huấn luyện

Mô hình long huấn luyện với hàm mất mát SmoothL1 (β = 0.02) có trọng số:
các mẫu gần ngưỡng hết vòng đời (SOH < 80%) được nhân trọng số 2× — vùng
quyết định thay pin cần chính xác nhất. Tối ưu hóa bằng AdamW
(lr = 5·10⁻⁴, weight decay = 3·10⁻⁴), dropout 0.3, nhiễu jitter 0.0075
trên đầu vào (data augmentation). Huấn luyện theo chiến lược warmup độ dài
lũy tiến 256 → 512 → 1024 → 2048 → 4096 (scheduler CosineAnnealingWarmRestarts,
T₀ = 3 trong các giai đoạn warmup, T₀ = 80 ở giai đoạn cuối); batch size 32;
chọn checkpoint theo MAE tốt nhất trên tập validation. Toàn bộ huấn luyện
thực hiện trên GPU Kaggle. Biến thể window-30 dùng cùng khung với
epochs = 50, early stopping patience = 10.

## 3.5 Phát hiện bất thường

Song song với hồi quy SOH, một IsolationForest (contamination = 0.1,
n_estimators = 100, seed 42) [cite: Liu, Ting & Zhou, ICDM 2008] được fit
trên đặc trưng phổ mức chu kỳ của TẬP HUẤN LUYỆN, không fit lại khi suy luận.
Do NASA dataset không có chú giải lỗi, chúng tôi định nghĩa nhãn bất thường
đại diện (proxy): một chu kỳ là bất thường nếu tốc độ suy thoái cục bộ
(chuỗi SOH làm mượt rolling-median, đạo hàm trung tâm) vượt phân vị 90 của
phân phối tốc độ trên tập huấn luyện (0.4833 %SOH/chu kỳ) — ngưỡng phân vị
90 nhất quán với contamination prior 0.1. Nhãn tuyệt đối theo ngưỡng EOL
(SOH < 80%) được báo cáo để đối chiếu nhưng suy biến trên các pin val/test
(≈98% mẫu dương). Đầu ra IsolationForest kết hợp với tầng sức khỏe SOH thành
ma trận rủi ro phục vụ quyết định bảo trì; đánh giá định lượng tại §4.6.

---

## Nguồn thông số (không đưa vào bài)

| Thông số | Nguồn |
|----------|-------|
| 6 kênh long = 4 base + IC + discharge progress | `scripts/preprocess_long.py` dòng 72–76, 235 (đã verify — plan cũ ghi "phase mask" là SAI) |
| Patch 16 / stride 8, d_state 32, attention 1 head, FiLM depth 2, dropout 0.3, jitter 0.0075, AdamW wd 3e-4, SmoothL1 β 0.02 + weighted, CAWR T₀=80 (warmup T₀=3) | metadata checkpoint `soh_mamba_long_v2.2.pth` |
| lr 5e-4, batch 32, VAL_BATCH 256 | `scripts/train.py` (BATCH_SIZE/LR) |
| Warmup stages 256→4096 | `src/core/config.py` WARMUP_STAGES |
| 57-dim = 10 spectral (incl. Gini) + 9 statistical × 3 kênh | `src/core/config.py` SPECTRAL_FEAT_DIM comment |
| Window-30: 6 features (V,I,T,t,cycle_norm,SOC), 79,467 params, d_state 16, epochs 50/patience 10 | `src/core/config.py` FEATURES + đếm params + rules |
| Số token 511 = (4096−16)/8+1 | công thức từ patch_size/stride trong checkpoint — nếu code pad khác thì sửa (⬜ verify khi rảnh, không chặn) |
| Nhãn anomaly rate-based p90 = 0.4833 %SOH/cycle | `logs/nckh/anomaly/table5.md` (GH-70) |
| Ambient temps 4/22/24/43(/44) | `metadata.csv` groupby (verify 2026-07-07) |
| MC Dropout 20 lượt | pipeline inference hiện tại (GH-62 batch 20 forward) |
