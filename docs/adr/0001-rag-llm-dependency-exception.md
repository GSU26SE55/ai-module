# ADR 0001 — Thêm chromadb / sentence-transformers / anthropic cho Prescription Layer

- **Status:** Accepted
- **Ngày:** 2026-06-26
- **Liên quan:** GH-20 (Prescription Layer), Phase 2 LLM enrichment
- **Context rule:** `.claude/rules/tech/ai.md` — "Không thêm ML framework ngoài PyTorch + scikit-learn"

## Context

Rule `ai.md` quy định AI module chỉ dùng **PyTorch + scikit-learn** (cho model SOH + Isolation Forest). Prescription Layer (GH-20) cần biến output prediction thành khuyến nghị bảo trì bằng RAG + LLM, đòi hỏi 3 thư viện ngoài rule đó:

- `chromadb` — vector store cho semantic retrieval knowledge base.
- `sentence-transformers` — embedding (`all-MiniLM-L6-v2`).
- `anthropic` — gọi Claude (Haiku 4.5) sinh prescription có cấu trúc.

## Decision

**Chấp nhận ngoại lệ có chủ đích** cho 3 thư viện trên, **giới hạn trong phạm vi lớp prescription** (`src/services/_llm_client.py`, `rag_retriever.py`, `scripts/ingest_rag.py`). Lý do giới hạn an toàn:

1. **Không đụng core model.** Rule `ai.md` về "không thêm framework" nhắm vào pipeline train/inference SOH. Lớp prescription là tầng *sau* prediction, không thay đổi kiến trúc Mamba/IsolationForest.
2. **Optional + graceful degradation.** Cả 3 lib là optional: thiếu chúng thì retriever trả `[]` và LLM trả `None` → hệ thống vẫn chạy bằng rule-based engine thuần Python. P1 hot-path không bao giờ chạm chúng.
3. **Có cơ sở khoa học.** RAG grounding + structured output là pattern chuẩn để LLM không bịa; phù hợp yêu cầu "cite paper/industry standard" của `ai.md` (B2).

## Consequences

- `requirements.txt` thêm `chromadb`, `sentence-transformers`, `anthropic` (đánh dấu optional, chỉ cần khi chạy `/prescribe` enrichment).
- `anthropic` phải đủ mới để hỗ trợ structured outputs (`output_config.format`) + `claude-haiku-4-5` — pin exact sau khi `pip install -U anthropic`.
- Core train/inference (`/predict`, `/health`) **không** phụ thuộc 3 lib này → môi trường training Kaggle không cần cài.
- Hội đồng KLTN: trình bày đây là exception có kiểm soát, không phải vi phạm "simplicity first".

## Alternatives đã cân nhắc

- **Rule-only (không LLM/RAG):** đơn giản nhất, đã là default/fallback. Nhưng thiếu khả năng diễn giải ngữ cảnh + trích dẫn SOP → giữ làm baseline, LLM chỉ *enrich*.
- **Tự viết embedding/retrieval bằng numpy:** tránh chromadb nhưng tăng maintenance, kém chuẩn hơn — không đáng cho scope capstone.

## Cập nhật path (GH-96, 2026-07-10)

`src/services/_llm_client.py` đã đổi thành package `src/services/prescription/llm/` (GH-79), sau đó toàn bộ lớp prescription (`prescription.py`, `rule_prescription.py`, `safety_gate.py`, `rag_retriever.py`, `llm/`) được gom vào subpackage `src/services/prescription/` (GH-96). Quyết định ngoại lệ dependency ở ADR này không đổi — chỉ đổi vị trí file.
