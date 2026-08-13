# Prescription Layer — Đánh giá & Kế hoạch phát triển

> Tài liệu nghiên cứu + kế hoạch cho lớp "prescription" (biến dự đoán AI thành khuyến nghị bảo trì hành động được).
> Ngày: 2026-06-22 · Trạng thái: PROPOSAL (chờ chốt governance)
> Cơ sở khoa học: Deng et al. (2024), *"From Prediction to Prescription: Large Language Model Agent for Context-Aware Maintenance Decision Support"*, PHM Society European Conference 2024, ISBN 978-1-936263-40-0.

---

## 0. TL;DR

- **Không** áp dụng *hoàn toàn* bài báo: lõi ML của paper (ROCKET + retrieval top-5 để **phân loại**) không hợp với dự án (dự án làm **regression SOH%** + anomaly 3 lớp, đã có Mamba + IsolationForest).
- **Có** áp dụng phần giá trị nhất: kiến trúc đa bước `predict → document-RAG → LLM tổng hợp → prescription + safety gate` (Figure 1b / nhánh "Database → LLM Summarization" của Figure 2).
- Đội đã khởi động đúng hướng ở branch **`feat/RAG_struct`** (commit `add RAG prescription skeleton`) — mới ~30%, phần LLM/KB/đánh giá/governance chưa xong.
- **Khuyến nghị**: đi **Phương án C (Hybrid)**, coi prescription là **track mở rộng (nice-to-have)**, **chốt governance package trước** (Phase 0).

---

## 1. Bài báo — lõi để áp dụng

Bài báo giải quyết **khoảng trống prediction → prescription**: model ML chỉ báo *cái gì sẽ hỏng*, không nói *xử lý thế nào*. Giải pháp = pipeline đa bước (Figure 1b):

```
Time series → [ROCKET encoder] → vector → [top-5 retrieval, RAG] → fault statement
            → [LLM sinh query] → [tool/DB search] → [LLM summarize] → báo cáo hành động
```

Điểm mấu chốt: đóng góp **không nằm ở độ chính xác** (ROCKET+top5 = 85%, chỉ ngang InceptionTime 83% — Table 1), mà ở việc **biến 1 nhãn dự đoán thành tài liệu bảo trì có ngữ cảnh, không cần train thêm, chống hallucination bằng RAG**, và có human-in-the-loop (nêu ở Future Work).

---

## 2. Đối chiếu bài báo ↔ dự án GSU26SE55

| Thành phần bài báo | Dự án của bạn | Áp dụng? |
|---|---|---|
| **Bài toán**: phân loại 13 fault rời rạc | Regression SOH% + anomaly 3 lớp (Normal/Degrading/Failed) | ⚠️ Khác bản chất |
| **ROCKET** (encoder training-free, 20k features) | Mamba SOH (đã train) + IsolationForest | ❌ ROCKET là *đối thủ thay thế*, không bổ trợ |
| **RAG = retrieval mẫu time-series để gán nhãn (kNN)** | — | ❌ Không cần (đã có Mamba) |
| **RAG = retrieval tài liệu để LLM tổng hợp** (bước DB→Summarize) | Chưa có | ✅ **Phần đáng giá nhất** |
| **LLM agent (GPT-4) sinh prescription** | Chưa có (output chỉ classification + SOH) | ✅ Áp dụng được (off hot-path) |
| **Tool/web search làm KB** | Cần KB bảo trì pin riêng | ✅ Thay bằng KB nội bộ + vector store |
| **Human verification** (chỉ nêu Future Work) | Cần cho P1 (an toàn) | ✅ Đội đã làm `safety_gate` — **tốt hơn paper** |

---

## 3. Phán quyết: KHÔNG áp dụng "hoàn toàn"

Bốn lý do cốt lõi:

1. **ROCKET không hợp.** Lõi ML của paper (ROCKET + Euclidean top-5) chính là *bộ phân loại* — **không làm regression SOH**, thứ là output chính của bạn. Đã có Mamba làm tốt. Thay Mamba bằng ROCKET là đi lùi + vi phạm rule "không thêm ML framework" (ROCKET nằm trong sktime/pyts).
2. **"RAG" trong paper ≠ "RAG" bạn cần.** Paper dùng RAG để *gán nhãn* (retrieve mẫu lịch sử giống nhau). Cái bạn cần là RAG **trên tài liệu văn bản** (SOP bảo trì, mã cảnh báo BMS, quy trình an toàn) để LLM *tổng hợp khuyến nghị* — đúng nhánh "Database → LLM Summarization" của Figure 2.
3. **Latency.** LLM mất *giây*, vi phạm SLA P1 `<100ms`. Prescription **bắt buộc tách khỏi** đường alert real-time. Skeleton đã tách đúng: `/predict` (nhanh) vs `/prescribe` (chậm, on-demand/async).
4. **Đụng rule cứng dự án.** `feat/RAG_struct` thêm `chromadb + sentence-transformers + anthropic` → **vi phạm trực tiếp** `ai.md`: *"KHÔNG thêm ML framework ngoài PyTorch + scikit-learn"* và *"không thêm package mới — hỏi Leader trước"*. **Phải chốt với Leader/GVHD trước.**

---

## 4. Hiện trạng skeleton `feat/RAG_struct`

Đội đã chuyển thể bài báo thông minh (dùng ChromaDB + sentence-transformers thay ROCKET; Claude thay GPT-4; thêm safety_gate).

| Đã làm tốt | Còn là stub / thiếu |
|---|---|
| Tách `/predict` ↔ `/prescribe` (không phá latency) | `_call_llm()` là **stub** — chưa gọi Anthropic thật |
| `safety_gate` (human verification, escalation) — paper chỉ nêu Future Work | `RagRetriever` fallback `[]` khi chưa có chromadb → KB **rỗng** |
| Embedding (sentence-transformer) thay ROCKET (gọn, hợp document-RAG) | Chưa có `knowledge/` (corpus) + `scripts/ingest_rag.py` |
| Schema response đủ evidence + ppe + escalation | Chưa có **đánh giá chất lượng prescription** |
| Dùng Claude `claude-sonnet-4-6` | Chưa có timeout / cache / fallback khi API lỗi |

Các file đã có trên branch (path lúc 2026-06-22; từ GH-96 các file `src/services/*` dưới đây đã gom vào subpackage `src/services/prescription/`):
- `src/routers/prescribe.py` — endpoint `POST /prescribe/`
- `src/services/prescription.py` — orchestrator: predict → query → retrieve → LLM → gate
- `src/services/rag_retriever.py` — ChromaDB + sentence-transformers (lazy import)
- `src/services/safety_gate.py` — human verification, thermal/electrical escalation
- `src/schemas/prescribe.py` — `PrescribeRequest` / `PrescribeResponse`

→ Khung kiến trúc **đúng**, mới ~30%.

---

## 5. Phản biện (rủi ro cho bảo vệ KLTN/NCKH)

- **"Đo chất lượng prescription bằng gì?"** — Regression có MAE/RMSE, classification có F1; prescription LLM **không có ground-truth dễ đo**. Phải thiết kế đánh giá (faithfulness vs KB, coverage, safety recall, human rating). Paper gốc *cũng né* phần này (chỉ 1 ví dụ định tính Figure 5) → nếu không chuẩn bị là điểm yếu chí mạng.
- **Hallucination + an toàn pin** — LLM khuyến nghị sai trên thiết bị điện áp cao = nguy hiểm thật. `safety_gate` đúng hướng nhưng cần: (1) LLM chỉ nói trong phạm vi KB đã retrieve; (2) human-in-the-loop bắt buộc cho mọi hành động vật lý, không chỉ P1.
- **Chi phí + phụ thuộc API ngoài** trong capstone "self-hosted Windows native" → cần fallback offline.
- **Scope creep** — `docs/nckh-plan.md` chỉ 3 tuần, trọng tâm kiểm chứng Mamba/RUL/latency, **không có** prescription. → Coi prescription là **track riêng**, không phải must-have của báo cáo chính.

---

## 6. Kế hoạch phát triển (theo phase)

> Mục tiêu: hoàn thiện prescription layer như **đóng góp mở rộng**, không đụng core Mamba/IsoForest, không phá latency, đủ chắc để bảo vệ.

### Phase 0 — Governance & quyết định (1–2 ngày, BẮT BUỘC trước)
- [ ] Chốt với Leader/GVHD: chấp nhận `chromadb`/`sentence-transformers`/`anthropic`? Nếu **không** → đi Phương án B (§7).
- [ ] Chốt phạm vi: must-have hay track mở rộng? (khuyến nghị: track mở rộng).
- [ ] Viết ADR ghi quyết định + cite bài báo làm Related Work.

### Phase 1 — Knowledge Base (corpus + ingest)
| File | Action | Nội dung |
|---|---|---|
| `knowledge/maintenance/*.md` | create | SOP bảo trì, ngưỡng SOH, quy trình thay thế (có citation) |
| `knowledge/safety/*.md` | create | Mã cảnh báo BMS, thermal runaway SOP, LOTO, PPE |
| `scripts/ingest_rag.py` | create | Chunk → embed → ghi ChromaDB vào `models/embeddings/`, **seed 42** |
| `models/embeddings/` | commit | Vector store build sẵn (như `scaler.pkl` phải commit) |

- Mỗi tài liệu KB **phải có citation** (giống yêu cầu B2 trong `ai.md`).

### Phase 2 — Hoàn thiện LLM call (thay stub)
- [ ] `_call_llm()`: gọi Anthropic (`claude-opus-4-8` hoặc `claude-sonnet-4-6`), **structured output** → `prescription / action_steps / ppe_required`.
- [ ] Prompt: *"chỉ dùng thông tin trong retrieved docs; thiếu thì nói 'cần chuyên gia'"* (chống hallucination).
- [ ] Timeout 10s, retry, **fallback rule-based** khi API lỗi.
- [ ] Cache theo `(action_code, risk_level, warning_codes)`.

### Phase 3 — Tích hợp ITIL (điểm cộng lớn, paper không có)
- [ ] `BatteryAnomalyDetectedEvent` → TicketService tạo ticket → gọi `/prescribe` (async) → enrich ticket bằng `action_steps` + `escalation_conditions`.
- [ ] `safety_gate.human_verification_required=True` → ticket chờ Manager duyệt, không auto-execute.
- [ ] Map `action_code`/`priority` prescription ↔ Priority Matrix P1/P2/P3 hiện có.

### Phase 4 — Đánh giá (quyết định điểm NCKH)
- [ ] Bộ test ~20–30 case (SOH/anomaly đa dạng) có **expert reference answer**.
- [ ] Metric: (a) *Faithfulness* — % câu truy được về KB; (b) *Coverage* — nêu đúng action bắt buộc; (c) *Safety recall* — % case nguy hiểm bị gate chặn đúng; (d) human rating 1–5.
- [ ] Ablation: LLM+RAG vs rule-based baseline vs LLM-no-RAG (chứng minh RAG có ích — tinh thần Table 1).
- [ ] Đo `rag_ms` + `llm_ms`, xác nhận **không nằm trong path P1 <100ms**.

### Phase 5 — Demo & báo cáo
- [ ] Notebook demo: reading → predict → prescribe → báo cáo (tái hiện Figure 5).
- [ ] Báo cáo: Related Work cite bài báo; nêu rõ *điểm khác* (regression vs classification, document-RAG vs sample-RAG, safety_gate là đóng góp mới).

---

## 7. Các phương án phát triển

### Phương án A — Full LLM+RAG (như §6)
Mạnh, "wow" khi demo; nhưng vướng rule package + chi phí + khó đánh giá. Hợp làm **track NCKH mở rộng**.

### Phương án B — Prescription rule-based (KHÔNG thêm framework) ⭐ nếu Leader từ chối package
- Bỏ ChromaDB/LLM. Dùng **bảng quyết định** `(action_code, risk_level, warning_codes) → template prescription + action_steps + PPE` bằng Python thuần.
- Vẫn output "prescriptive", vẫn có `safety_gate`, **đạt <100ms**, **0 phụ thuộc ngoài**, deterministic → dễ đánh giá & bảo vệ.
- Đây là Figure 1(a) "rule-based" của paper — paper chê khó mở rộng, nhưng với scope capstone (3 lớp, ~15 anomaly type) thì **đủ và an toàn hơn**.

### Phương án C — Hybrid ⭐⭐ khuyến nghị
- Rule-based làm **đường mặc định + fallback** (luôn chạy, <100ms, an toàn).
- LLM+RAG làm **lớp làm giàu async** chỉ cho P2/P3 hoặc khi user bấm "giải thích chi tiết".
- → Giữ SLA + có đóng góp LLM để viết báo cáo + có ablation rule vs LLM vs hybrid.

### Mở rộng theo Future Work của paper
- *Univariate → multivariate*: bạn đã dùng 3 features (V/I/T) → **đã vượt paper** (paper chỉ dùng current). Ghi vào báo cáo như điểm mạnh.
- *Frequency domain*: repo đã có `spectral_kurtosis` (branch `feat/spectral_kurtosis`) — đúng hướng paper đề xuất → tận dụng làm feature/đóng góp.
- *Long-term memory*: lưu prescription đã duyệt vào KB để retrieve lần sau (self-improving) — match "From Ad-hoc to Long-Term Memory".

---

## 8. So sánh nhanh 3 phương án

| Tiêu chí | A — Full LLM+RAG | B — Rule-based | C — Hybrid |
|---|---|---|---|
| Latency hot-path | ❌ giây | ✅ <100ms | ✅ <100ms (rule default) |
| Phụ thuộc ngoài | chromadb+ST+anthropic | ✅ không | có (chỉ nhánh async) |
| Vướng rule package | ❌ có | ✅ không | ⚠️ một phần |
| Chất lượng khuyến nghị | cao, linh hoạt | cứng, giới hạn | cao + an toàn |
| Dễ đánh giá/bảo vệ | khó | dễ | dễ (có ablation) |
| Chi phí | API cost | 0 | thấp |
| "Wow" demo | cao | thấp | cao |

---

## 9. Bước tiếp theo đề xuất

1. **Chốt Phase 0** (governance) — quan trọng nhất.
2. Tạo ADR `docs/adr/00xx-prescription-layer.md` từ tài liệu này.
3. Nếu duyệt Phương án C → mở GitHub Issue qua `/kltn-task` → `/kltn-plan`.
