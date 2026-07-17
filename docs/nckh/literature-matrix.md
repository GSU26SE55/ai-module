# Literature Matrix — §2 Related Work (mục tiêu 12–18 refs)

> Quy trình: mình search → điền cột Nguồn tìm/Ghi chú → **user đọc + xác nhận**
> (cột "Đã đọc?") → chỉ ref có ✅ mới được đưa vào References chính thức.
> IRON RULE: verify DOI/link mở được thật trước khi trích trong bài.

## Nhóm 1 — SOH truyền thống (ECM/Kalman) — mục tiêu 2–3 bài

| # | Tác giả–Năm | Phương pháp | Dataset | Split protocol | Kết quả | Gap so với mình | Nguồn | Đã đọc? |
|---|---|---|---|---|---|---|---|---|
| 1.1 | ⬜ TODO — Adaptive Unscented Kalman Filter (SOC+SOH đồng thời) | AUKF trên equivalent circuit model | Chưa rõ (cần đọc) | N/A (model-driven, không train/test split kiểu ML) | Chưa rõ | Đại diện dòng model-driven — chi phí tính toán thấp nhưng nhạy với sai lệch mô hình mạch điện, không tổng quát hóa cross-battery được như data-driven | ScienceDirect S2352484722018170 — ⚠️ 403 chặn bot, **user tự mở link** | ⬜ Chưa đọc |
| 1.2 | ⬜ TODO (tên tác giả chưa lấy được, MDPI 403 chặn bot) — "The State of Health Estimation of Lithium-Ion Batteries: A Review of Health Indicators, Estimation Methods, Development Trends and Challenges" | Review — phân loại model-based (EM, ECM) vs data-driven (LR, GPR, SVR, LSTM...) | — (review, không có dataset riêng) | — | — | Dùng để viết câu mở đầu §2 mạch 1, đúng cấu trúc "phân 2 nhóم model-driven/data-driven" mà plan đã định | World Electric Vehicle Journal (MDPI, ISSN 2032-6653), vol 16, issue 8, article 429 — **user tự mở link lấy tên tác giả**: https://www.mdpi.com/2032-6653/16/8/429 | ⬜ Chưa đọc |

## Nhóm 2 — Deep learning cho SOH — mục tiêu 4–5 bài

| # | Tác giả–Năm | Phương pháp | Dataset | Split protocol | Kết quả | Gap so với mình | Nguồn | Đã đọc? |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Patel, Ramezankhani, Deodhar, Birru (2025) — TIDSIT | Time-Informed Dynamic Sequence-Inverted Transformer (hidden dim 42, 8 attention heads, 1 encoder layer) | NASA (train B0005+B0006, test B0007) | **Cross-battery** nhưng NHỎ HƠN nhiều: chỉ 2 pin train / 1 pin test (so với 23/2/1 của mình), không có LOBO, không báo cáo param count, KHÔNG có latency | RMSE 0.58% trên B0007 (giảm >50% so với LSTM baseline RMSE 0.82%) | **Đối thủ trực tiếp thứ 3** (sau SambaMixer, CNN-LSTM baseline của mình): họ chính xác hơn nhưng protocol yếu hơn hẳn — chỉ 3 pin tổng cộng, không robustness test, không param/latency. Nên thêm 1 câu ở §5.3 giống SambaMixer nhưng nhấn mạnh khác biệt độ nghiêm ngặt protocol | arXiv:2507.18320 (07/2025, rev 11/2025) | ✅ **AI-verified qua fetch full-text 12/07** — user nên tự đọc lướt trước khi trích chính thức |
| 2.2 | Dubarry, Costa, Matthews (2023) — Nature Communications | So sánh 5 thuật toán (RF, XGBoost, FNN, 1D-CNN, DTW-CNN) trên dữ liệu PV+battery TỔNG HỢP (synthetic, mô phỏng bức xạ mặt trời) | PV + Li-ion, KHÔNG phải lab-cycling như NASA — synthetic, biến thiên cell-to-cell | Đánh giá theo kịch bản (same-day/khác ngày/trời mây), KHÔNG phải cross-battery holdout đơn giản | RMSE 0.66–3.55% tùy kịch bản; **2.75%** là số cho >10,000 đường suy thoái ≤25% degradation (không phải số headline duy nhất) | Baseline hay được trích, nhưng protocol khác hẳn (synthetic + solar irradiance-driven, không phải cycle-based như NASA) — khi trích phải ghi rõ scope "RMSE 2.75% trên tập con ≤25% degradation", không nói chung chung | PMC10229535, *Nat Commun* 2023 | ✅ AI-verified (fetch 13/07) |
| 2.3 | CNN-LSTM-Attention (2024) — MDPI Batteries | CNN (local) + LSTM (temporal) + Attention | Chưa rõ | Chưa rõ | Alarm rate ~5%, cross-battery generalization (claim) | Kiến trúc gần baseline CNN-LSTM của mình + có Attention — đáng so trực tiếp cách dùng attention | mdpi.com/2313-0105/11/10/384 | ⬜ Chưa đọc full-text |
| 2.4 | ⬜ TODO — Transformer-Based Transfer Learning | Transformer, pretrain NASA → fine-tune Oxford | NASA (pretrain) + Oxford (fine-tune) | Cross-dataset transfer (khác cross-battery nhưng liên quan) | RMSE 0.01461 (Oxford), thắng ANN 17% | Transformer cùng NASA — góc nhìn transfer learning, không phải cross-battery trực tiếp | doi:10.3390/en18205439 (MDPI Energies 2024) | ⬜ Chưa đọc full-text |

## Nhóm 3 — Mamba/SSM cho pin — mục tiêu 3–4 bài

| # | Tác giả–Năm | Phương pháp | Dataset | Split protocol | Kết quả | Gap so với mình | Nguồn | Đã đọc? |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Olalde-Verano, Kirch, Pérez-Molina, Martín (2025) — SambaMixer | MambaMixer (channel+token selective SSM), anchor resampling, sample-time positional encoding | NASA PCoE | Cross-battery (NASA-L: train 10 pin, eval #6/7/47) | MAE 0.51–1.20% (SambaMixer-L, 48.7M params); XL (85.6M) tệ hơn L | Họ chính xác hơn nhưng 490× tham số, không báo cáo latency. Positioning: hiệu quả + deployability. Song song: cùng thấy extrapolation fail vùng SOH hiếm + model to hơn overfit — 2 điểm đã trích trong §4.4a/§5.2/§5.3 | arXiv:2411.00233, IEEE Access vol.13 2025 | ✅ **User đọc full-text 12/07** |
| 3.2 | ⬜ TODO — MambaLithium (arXiv:2403.05430, 2024) | Selective SSM cho RUL/SOH/SOC | Chưa rõ (abstract không nêu) | Chưa rõ | Chưa rõ | ⚠️ arXiv tự gắn cờ "trùng lặp văn bản đáng kể" với arXiv:2402.18959 — CẨN THẬN, có thể nên đọc/trích bài gốc (2402.18959) thay vì bài này | arXiv:2403.05430 | ⬜ Chưa đọc full-text |
| 3.3 | ⬜ TODO — U-H-Mamba (MDPI Energies, 2025/2026) | Hierarchical uncertainty-aware SSM, RUL | Hybrid lab + real-world EV (146k+ cycles) | Chưa rõ | Chưa rõ | Domain khác (RUL không phải SOH nowcasting; có real-world data — điểm mạnh cần nhắc) | MDPI Energies (vol 19, no 2, 414) | ⬜ Chưa đọc full-text |
| 3.4 | ⬜ TODO — Multimodal Mamba-battery | Fusion discharge curves + impedance spectra qua Mamba | Chưa rõ | Chưa rõ | Chưa rõ | Hướng khác (multimodal input) — có thể chỉ cite 1 câu, không cần so số | doi:10.3390/batteries12060196 (MDPI Batteries) | ⬜ Chưa đọc full-text |
| 3.5 | Crocioni et al. (2020) — "Li-ion batteries parameter estimation with tiny neural networks embedded on intelligent IoT microcontrollers" | So sánh CNN/LSTM/GRU/CNN-LSTM/CNN-GRU, quantize + deploy lên STM32 microcontroller (X-CUBE-AI toolchain) | NASA PCoE | Chưa rõ chi tiết split | CNN-GRU cho kết quả tốt kể cả sau quantization | ⚠️ Không phải Mamba (kiến trúc cũ CNN/RNN) — đặt ở đây vì cùng chủ đề deployability, không phải Mamba-battery. **Đối chứng mạnh nhất cho claim <100ms**: microcontroller còn hạn chế hơn CPU thường nhiều — nếu họ làm được trên MCU thì <100ms CPU của mình rất khả thi, đáng trích trong §1/§5.4 phần deployability | IEEE Access, vol 8, tr 122135–122146, 2020 | ✅ AI-verified (search 13/07, chưa fetch full-text) |

## Nhóm 4 — Citations phương pháp (6 bài "must-have", seminal)

| # | Kỹ thuật | Paper | Nguồn (verify DOI) | Đã đọc? |
|---|----------|-------|-------------------------|---------|
| 4.1 | Mamba | Albert Gu, Tri Dao — "Mamba: Linear-Time Sequence Modeling with Selective State Spaces", **COLM 2024** (venue chính thức — cite COLM thay vì arXiv:2312.00752; xác nhận chéo qua ref [16] bài draft của GVHD 17/07) | arXiv:2312.00752 / COLM 2024 | ✅ AI-verified (fetch 12/07, venue update 17/07) |
| 4.2 | FiLM | Ethan Perez, Florian Strub, Harm de Vries, Vincent Dumoulin, Aaron Courville (2018) — "FiLM: Visual Reasoning with a General Conditioning Layer", AAAI 2018 | arXiv:1709.07871 | ✅ AI-verified (fetch 12/07) |
| 4.3 | Isolation Forest | Fei Tony Liu, Kai Ming Ting, Zhi-Hua Zhou (2008) — "Isolation Forest", ICDM 2008, tr. 413–422 | DOI: 10.1109/ICDM.2008.17 | ✅ AI-verified (search 12/07) |
| 4.4 | MC Dropout | Yarin Gal, Zoubin Ghahramani (2016) — "Dropout as a Bayesian Approximation: Representing Model Uncertainty in Deep Learning", ICML 2016 | arXiv:1506.02142 | ✅ AI-verified (fetch 12/07) |
| 4.5 | Patch encoding | Yuqi Nie, Nam H. Nguyen, Phanwadee Sinthong, Jayant Kalagnanam (2023) — "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers" (PatchTST), ICLR 2023 | arXiv:2211.14730 | ✅ AI-verified (fetch 12/07) |
| 4.6 | NASA dataset | B. Saha, K. Goebel (2007) — "Battery Data Set", NASA Ames Prognostics Data Repository, NASA Ames Research Center, Moffett Field, CA | https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/ | ✅ AI-verified (search 12/07) |

---

## Trạng thái tổng (cập nhật 12/07 — user yêu cầu mình đọc thay)

- **8/18 đã AI-verify** (SambaMixer đọc full-text từ user cung cấp; TIDSIT + 6 bài seminal đọc qua fetch/search hôm nay).
- ⚠️ **Lưu ý về "AI-verified" khác "user đã đọc"**: 7 dòng mới (TIDSIT + 6 seminal) mình đọc/tóm tắt bằng công cụ fetch, KHÔNG phải bạn tự đọc. Với 6 bài seminal (kỹ thuật nền tảng, ít rủi ro diễn giải sai) — dùng được luôn, rủi ro thấp. Với **TIDSIT** — vì đây là đối thủ trực tiếp có thể ảnh hưởng đến claim của bài (giống SambaMixer), khuyến nghị bạn tự đọc lướt qua abstract 1 lần trước khi hội đồng hỏi, để có thể tự trả lời nếu bị hỏi sâu — mình tóm tắt có thể bỏ sót sắc thái.
- **10/18 còn lại** (1.1, 1.2, 2.2–2.4, 3.2–3.5) chưa động tới — nói tiếp nếu muốn mình đọc luôn nốt.
- **2 link bị chặn bot (403)** — 1.1 (ScienceDirect), 1.2 (MDPI) — mình không fetch được, cần bạn tự mở (không có cách nào khác).

### Phát hiện quan trọng nhất hôm nay — TIDSIT là đối thủ thứ 3

Train B0005+B0006, test B0007 (cross-battery, nhưng **chỉ 3 pin tổng cộng** — protocol yếu hơn hẳn 26 pin + LOBO của mình). RMSE 0.58% trên B0007 — tốt hơn số của mình, nhưng KHÔNG có: param count, latency, robustness test nào. Đã thêm 1 dòng vào §5.3 phía dưới — xem đoạn mới trong `section5-discussion-vi.md`.

## Bước tiếp theo

Muốn mình đọc nốt 10 dòng còn lại luôn không, hay dừng ở đây để bạn tự đọc phần còn lại?
