# Paper Plan — NCKH

**Title:** *Mamba State Space Model with Spectral Feature Conditioning for State of Health Prediction and Anomaly Detection in Lithium-Ion Batteries*

> Chapter Plan sinh bởi academic-paper skill (plan mode). Trạng thái: APPROVED (title do user chốt 2026-07-03).

## Paper Configuration Record

| Mục | Giá trị |
|-----|---------|
| Paper type | Conference paper (IMRaD, IEEE 2-column style) |
| Scope | **Mamba SOH prediction + IsolationForest anomaly detection** (RAG/prescription → future work). Scope mở rộng theo title user chốt — kéo theo nghĩa vụ evaluation anomaly (F1 > 0.80). |
| Language | English (abstract song ngữ EN + VI) |
| Venue | NCKH sinh viên / hội nghị cấp trường — 6–8 trang |
| Headline result | Long-seq L=4096: **MAE 1.63% / RMSE 2.09%** trên pin 4°C held-out |
| Citation format | IEEE |
| Authors | Team GSU26SE55, FPT University |

## Thesis Statement (1 câu)

> A patch-based Mamba state-space model with FiLM conditioning on cycle-level spectral features predicts lithium-ion battery SOH from full-cycle raw telemetry (L=4096) with MAE 1.63% under a strict cross-battery, cross-temperature (4°C held-out) evaluation protocol — while a compact 30-step variant sustains <100 ms CPU inference for real-time deployment.

## Contribution Claims (3 — dùng làm bullet cuối Introduction)

1. **Architecture**: pure-PyTorch Mamba (no CUDA kernel dependency) với patch encoder P16S16 nén L=4096→256 tokens, FiLM conditioning trên 57-dim spectral+kurtosis+Gini features, kênh IC curve (dQ/dV) + phase mask.
2. **Evaluation protocol**: cross-battery split 23/2/1 trên NASA Ames (26 pin), val/test là pin 4°C model chưa từng thấy — đo generalization thật thay vì chia timestep trong 1 pin; kèm leave-one-battery-out mean±std.
3. **Deployment-awareness**: biến thể window=30 (~66k params) inference <100 ms CPU — khả thi cho giám sát pin solar thời gian thực.

---

## Chapter Plan

### 1. Introduction (~0.75 trang, ~600 từ)
- **Câu chuyện**: pin Li-ion trong hệ solar backup → bảo trì dự đoán cần SOH chính xác → deep learning hiện tại (LSTM/CNN-LSTM/Transformer) giới hạn ở cửa sổ ngắn hoặc chi phí attention O(L²) → Mamba SSM tuyến tính theo L, phù hợp full-cycle telemetry.
- **Gap (1 câu)**: các nghiên cứu Mamba cho pin hiện tập trung dự đoán số trên split dễ (chia timestep cùng pin); thiếu đánh giá cross-battery + cross-temperature và thiếu quan tâm deployability.
- Kết chương bằng 3 contribution claims ở trên.
- **Cảm giác reader cần có**: "split kiểu cũ đang thổi phồng kết quả — bài này đánh giá kiểu khó".

### 2. Related Work (~0.75 trang, ~500 từ) — 3 mạch
1. SOH estimation truyền thống: ECM + Kalman/particle filtering; ưu/nhược.
2. Deep learning cho SOH: LSTM, CNN-LSTM, Transformer — trích 3–5 bài, chỉ ra split protocol của từng bài (điểm tựa cho claim protocol).
3. SSM/Mamba cho time series + các bài Mamba-battery đầu tiên → định vị: khác họ ở protocol + spectral FiLM + deployability.
- ⚠️ IRON RULE: mọi citation phải verify DOI thật trước khi vào nháp — TODO cần chạy literature search, chưa có sẵn trong repo.

### 3. Methodology (~2 trang, ~1300 từ)
- **3.1 Dataset & protocol**: NASA Ames 26 pin; discharge cycles; SOH = capacity/2.0Ah×100; split 23 train / 2 val (B0046/47, 4°C) / 1 test (B0048, 4°C held-out); loại B0036, B0049–52, B0038–40 (lý do nhiễu/corrupt); seed 42.
- **3.2 Features**: 4 kênh raw (V, I, T, t) + IC curve dQ/dV + phase mask = 6 kênh long-seq; 57-dim cycle-level features (10 spectral incl. Gini + 9 statistical × 3 kênh) — tính trên FULL cycle.
- **3.3 Architecture**: MambaBlock (toán tắt gọn 3–4 công thức); patch encoder P16S16 (4096→256 tokens); FiLM: feature vector → (γ, β) điều biến hidden states; attention pooling; d_state=32.
- **3.4 Training**: loss SmoothL1, CosineAnnealingWarmRestarts (T₀=25), progressive length warmup 256→4096, batch/lr/epochs từ config.
- **3.5 Anomaly detection** (theo title): IsolationForest (contamination=0.1, n_estimators=100, seed 42) fit trên cycle-level spectral features của train set; mapping score → Normal/Warning/Anomaly (ngưỡng −0.1/−0.3); kết hợp với SOH health stage thành risk matrix. Cite Liu et al. ICDM 2008 cho hyperparameters (đã justify trong `.claude/docs/ai-research-references.md` §B2).
- **Câu hỏi phòng thủ**: "Sao không dùng mamba-ssm CUDA?" → tính di động (Windows/CPU); "Sao không Transformer?" → O(L²) tại L=4096 + bảng so sánh (nếu kịp chạy) hoặc cite.

### 4. Experiments & Results (~2 trang, ~1200 từ)
- **Table 1 — Main results**: Long Mamba vs window-30 Mamba vs LSTM baseline vs naive (last-SOH) — MAE/RMSE trên B0048. ❗ *cần chạy: LSTM cùng protocol*.
- **Table 2 — LOBO robustness**: mean±std MAE across folds. ❗ *cần chạy: `experiment_nowcast_lobo.py`*.
- **Table 3 — Ablation**: d_state 16↔32 (GH-34), features 6↔4 (GH-25), attention pooling on/off (GH-37), FiLM on/off — lấy từ log các GH đã làm + chạy bù ô thiếu.
- **Table 4 — Latency**: window-30 CPU <100ms (benchmark script có sẵn), long model GPU/CPU.
- **Table 5 — Anomaly detection** (bắt buộc vì title): Precision/Recall/F1 (target F1 > 0.80). ❗ *cần thiết kế ground truth trước: đề xuất label cycle có SOH < 80% (EOL) hoặc thuộc vùng suy thoái nhanh là anomalous, rồi đánh giá IsolationForest trên val/test — phải mô tả rõ định nghĩa label trong bài để không bị hỏi "anomaly ground truth từ đâu ra?"*.
- **Figures**: (F1) kiến trúc pipeline; (F2) predicted vs true SOH curve trên B0048; (F3) ablation bar chart. Vẽ bằng matplotlib theo chuẩn publication.
- **Finding quan trọng nhất (1 câu)**: model long-seq generalize sang pin + nhiệt độ chưa thấy với MAE 1.63%, vượt target 2%.

### 5. Discussion (~0.5 trang, ~400 từ)
- Vì sao spectral FiLM giúp: degradation signature nằm ở tần số/kurtosis mà raw window ngắn không thấy.
- Error analysis: sai số tập trung ở đâu trên B0048 (đầu/cuối đời pin?) — ❗ *cần phân tích residual khi có model cuối*.
- **Limitations (bắt buộc, thành thật)**: (1) 1 pin test duy nhất → LOBO bù; (2) data phòng lab cycle-based, chưa phải field telemetry BMS; (3) chưa so trực tiếp Transformer cùng protocol.

### 6. Conclusion (~0.25 trang, ~200 từ)
- Đoạn duy nhất cần nhớ: protocol khó + kiến trúc nhẹ + kết quả đạt chuẩn.
- Future work: RUL, anomaly+risk mapping, RAG prescription layer (trỏ về hệ thống capstone).

### Mandatory back-matter
Data Availability (NASA public dataset + repo), AI-usage disclosure, Author Contributions (CRediT), Acknowledgment (GVHD Trương Long).

---

## Kết quả cần thu thập trước khi viết Section 4 (thứ tự ưu tiên)

| # | Việc | Công cụ có sẵn | Chặn section |
|---|------|----------------|--------------|
| 1 | Chốt model + số cuối (v1.3 Kaggle hoặc long v2.x) | notebook Kaggle | Toàn bài |
| 2 | LSTM/CNN-LSTM baseline cùng protocol | cần thêm nhánh train LSTM (arch có trong rules) | Table 1 |
| 3 | LOBO mean±std | `scripts/experiment_nowcast_lobo.py` | Table 2 |
| 4 | Gom số ablation từ logs GH-25/34/37/38, chạy bù ô thiếu | logs/ + train.py flags | Table 3 |
| 5 | Benchmark latency chính thức | `tests/test_inference.py`, `benchmark_grpc.py` | Table 4 |
| 6 | Literature search + verify DOI (8–15 refs) | deep-research skill | Section 2 |
| 7 | Anomaly evaluation: định nghĩa ground truth label + chạy P/R/F1 trên val/test | cần viết `scripts/eval_anomaly.py` (~50 dòng) | Table 5 |

## Argument Stress Test (điểm yếu nhất → cách đỡ)

1. **"MAE 1.63% có SOTA không?"** — Không claim SOTA. Claim: đạt target công nghiệp (<2%) dưới protocol khó hơn chuẩn mực phổ biến. So sánh số giữa các bài khác split là không hợp lệ — nói thẳng điều này trong Discussion.
2. **"1 pin test?"** — LOBO mean±std là câu trả lời; nếu chưa chạy kịp thì đây là điểm chết của bài → ưu tiên #3 ở trên.
3. **"Mamba cho pin đã có người làm"** — Không claim "first". Claim tổ hợp: protocol + spectral FiLM + pure-PyTorch deployability. Related work phải cite các bài Mamba-battery có thật để chứng minh mình biết họ.
4. **"Anomaly ground truth từ đâu?"** (mới, do title thêm anomaly) — NASA dataset không có nhãn anomaly. Phải định nghĩa label rõ ràng (đề xuất: EOL-based) và thừa nhận trong Limitations rằng đây là proxy label, không phải fault annotation thật.

## INSIGHT bổ sung

- `[INSIGHT: paper_title]` (user chốt 2026-07-03): *Mamba State Space Model with Spectral Feature Conditioning for State of Health Prediction and Anomaly Detection in Lithium-Ion Batteries*.
- `[INSIGHT: workflow]` — user tự viết tiếng Việt đầy đủ trước, gom lại rồi translate sang English. Abstract đã viết xong (2026-07-03). User tự làm literature review theo guide bên dưới.
- Abstract cần khớp lại 3 điểm: 54→57 dim (Gini); tách rõ 2 cấu hình model (long L=4096 cho accuracy vs window-30 cho <100ms CPU); chốt 1 taxonomy phân loại (health_stage 4 mức + anomaly_status 3 mức, không dùng Normal/Degrading/Failed cũ).

---

## Danh sách hình ảnh & bảng (chốt cho bản nháp)

### Hình (6 hình, ưu tiên theo thứ tự)

| # | Hình | Section | Cách tạo |
|---|------|---------|----------|
| F1 | **Kiến trúc tổng thể** — pipeline: raw telemetry → preprocessing → patch encoder → MambaBlock×2 + FiLM(spectral 57-dim) → attention pooling → SOH head; nhánh song song IsolationForest → risk matrix | §3 | Vẽ draw.io/PowerPoint → export PDF/SVG. Hình quan trọng nhất bài |
| F2 | **Predicted vs True SOH** trên B0048 (test held-out) — trục x: cycle, trục y: SOH%, 2 đường + vùng uncertainty (MC Dropout ±std) | §4 | matplotlib từ output model cuối; script eval có sẵn nền tảng trong experiment scripts |
| F3 | **Cấu trúc MambaBlock + FiLM** — zoom vào 1 block: in_proj → conv1d → SSM scan → FiLM(γ,β từ spectral vector) → out_proj | §3 | draw.io; tham khảo hình gốc paper Mamba rồi vẽ lại theo kiến trúc mình |
| F4 | **Ablation bar chart** — MAE theo từng biến thể: full model / bỏ FiLM / bỏ IC curve / d_state 16 / features 6→4 | §4 | matplotlib, data từ Table 3 |
| F5 | **Dataset overview** — SOH degradation curves của 26 pin, tô màu theo split (train/val/test), làm nổi bật nhóm 4°C | §3.1 | matplotlib từ metadata.csv — thuyết phục trực quan là protocol khó |
| F6 | **Anomaly score distribution** — histogram IsolationForest score trên val/test, đánh dấu ngưỡng −0.1/−0.3 | §4 (Table 5 đi kèm) | matplotlib sau khi có eval_anomaly.py |

Quy tắc: vector (PDF/SVG), font ≥8pt khi in 2 cột, colorblind-safe, mỗi hình phải được refer trong text.

### Bảng (5 bảng — đã liệt kê ở Section 4 plan): main results, LOBO, ablation, latency, anomaly P/R/F1.

---

## Hướng dẫn tự tìm reference (user tự làm literature review)

### Nguồn tìm
1. **Google Scholar** (chính) — sort by citations, lọc từ 2020 cho DL papers
2. **arXiv** (cs.LG) — cho Mamba/SSM papers mới nhất
3. **IEEE Xplore** — cho battery SOH papers (nhiều bài IEEE Trans. nhất)
4. Mẹo: tìm 1 bài survey SOH deep learning gần đây → mine reference list của nó

### Từ khóa theo từng mạch Related Work

**Mạch 1 — SOH truyền thống (2–3 refs):**
- `"state of health" estimation "equivalent circuit model" Kalman filter lithium-ion`
- `battery SOH estimation review`

**Mạch 2 — Deep learning cho SOH (4–5 refs):**
- `LSTM "state of health" lithium-ion NASA dataset`
- `CNN-LSTM battery SOH prediction`
- `Transformer battery state of health estimation`
- ⚠️ Với mỗi bài: **ghi lại split protocol của họ** (chia timestep hay chia pin?) — đây là đạn cho contribution claim #2

**Mạch 3 — Mamba/SSM (3–4 refs):**
- `Mamba selective state space model` (bài gốc Gu & Dao 2023, arXiv 2312.00752)
- `Mamba time series forecasting`
- `Mamba battery state of health` / `state space model battery prognostics` — BẮT BUỘC tìm để biết ai đã làm trước, tránh claim "first"

**Citations phương pháp (5 bài "must-have", tìm dễ vì đều seminal):**
| Kỹ thuật trong bài | Paper cần tìm |
|--------------------|---------------|
| Mamba | Gu & Dao, 2023 — "Mamba: Linear-Time Sequence Modeling with Selective State Spaces" |
| FiLM | Perez et al., AAAI 2018 — "FiLM: Visual Reasoning with a General Conditioning Layer" |
| Isolation Forest | Liu, Ting & Zhou, ICDM 2008 — "Isolation Forest" |
| MC Dropout | Gal & Ghahramani, ICML 2016 — "Dropout as a Bayesian Approximation" |
| Patch encoding | Nie et al., ICLR 2023 — "A Time Series is Worth 64 Words" (PatchTST) |
| NASA dataset | Saha & Goebel — NASA Ames Prognostics Data Repository (citation chuẩn trên trang NASA) |

### Quy trình screening (làm cho mỗi bài tìm được)
1. Đọc abstract — có liên quan trực tiếp không? Không → bỏ
2. Ghi vào **literature matrix** (bảng Excel/Notion): `Tác giả-Năm | Phương pháp | Dataset | Split protocol | MAE/RMSE | Gap so với mình`
3. **Verify DOI tồn tại thật** (mở link DOI ra được paper) — IRON RULE, không được để citation ma
4. Đích: **12–18 refs** cho bài 6–8 trang; >10 năm tuổi chỉ giữ nếu seminal

### Literature matrix chính là Section 2
Viết xong matrix thì Section 2 gần như tự viết: mỗi mạch 1 đoạn tổng hợp từ matrix + 1 câu chốt "vì vậy còn thiếu X" dẫn về gap của mình.

## INSIGHT Collection

- `[INSIGHT: thesis_statement]` — như trên.
- `[INSIGHT: contribution_claim]` — 3 claims: architecture / protocol / deployability (nguồn: gap statement user phác trong docs/agent-review-brief.md §11 + lựa chọn scope của user).
- `[INSIGHT: headline]` — long-seq MAE 1.63%, user chọn.
- Open question carried forward: tên gọi chính thức của model trong bài (đề xuất cần user đặt: "SolarMamba"? "SpectraMamba"?).
