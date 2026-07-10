# ADR 0003 — Multi-provider LLM chain (DeepSeek chính, Gemini backup) cho Prescription Layer

- **Status:** Accepted
- **Ngày:** 2026-07-09
- **Liên quan:** GH-20/22 (nền hybrid prescription), GH-79 (provider chain), GH-24 (eval sẽ đo chất lượng per-provider)
- **Context rule:** `.claude/rules/tech/ai.md` — "Không thêm ML framework ngoài PyTorch + scikit-learn"; nối tiếp ngoại lệ đã mở trong [ADR 0001](0001-rag-llm-dependency-exception.md)

## Context

ADR 0001 chấp nhận `anthropic` làm ngoại lệ có kiểm soát cho lớp prescription (`enrich=true`). Từ đó phát sinh vấn đề: `src/services/_llm_client.py` hard-code **1 provider duy nhất** (Anthropic Claude Haiku) — khi API lỗi/hết quota/thiếu key, `enrich` rơi thẳng về rule-based, không có LLM backup nào khác. Team quyết định đổi sang **DeepSeek làm provider chính, Gemini làm backup**, với 2 lý do: chi phí thấp hơn Anthropic cho volume lớn, và có backup thật sự thay vì rơi thẳng về rule-based khi provider chính lỗi.

## Decision

Mở rộng ngoại lệ ADR 0001 để **thêm 2 dependency mới**, cùng giới hạn phạm vi (chỉ lớp prescription, không đụng core Mamba/IsolationForest):

- `openai` — SDK dùng gọi DeepSeek qua endpoint OpenAI-compatible (`base_url=https://api.deepseek.com`, model `deepseek-chat`).
- `google-genai` — SDK gọi Gemini (`gemini-2.5-flash`) làm backup tầng 2.

`anthropic` **không bị xoá** — giữ lại như 1 provider tuỳ chọn trong chain (backward compat, ai có key thì dùng được), nhưng không còn là default.

Kiến trúc: `src/services/_llm_client.py` (1 file) → package `src/services/llm/` gồm interface `LLMProvider` (`base.py`) + 3 implementation (`deepseek_provider.py`, `gemini_provider.py`, `anthropic_provider.py`) + orchestrator fallback (`chain.py`, đọc thứ tự từ env `LLM_PROVIDER_CHAIN`, default `deepseek,gemini`).

```
enrich=true → [RAG retrieve] → DeepSeekProvider (chính)
                                  ↓ lỗi/timeout/malformed
                               GeminiProvider (backup)
                                  ↓ lỗi/timeout/malformed
                               rule-based (luôn có sẵn — không đổi, GH-20)
```

Lý do giới hạn an toàn giữ nguyên như ADR 0001:

1. **Không đụng core model** — chỉ thay đổi trong `src/services/llm/` + `prescription.py::_enrich()`, pipeline `/predict` (Mamba + IsolationForest) không đổi.
2. **Optional + graceful degradation** — mọi provider optional; không key nào set → rule-based, `llm_provider="none"`, P1 hot-path (`enrich=false`) không bao giờ chạm mạng.
3. **Contract downstream không đổi** — schema `emit_prescription` (`prescription`/`action_steps`/`ppe_required`) giữ nguyên cho cả 3 provider; `prescription.py` chỉ thêm field `llm_provider` để trace, không đổi logic union PPE/fallback.

Quyết định do người phụ trách prescription (đủ thẩm quyền quyết định trực tiếp trong dự án này, không qua GVHD — xem quyết định tương tự cho headline NCKH) duyệt, không cần chờ họp Leader riêng cho ngoại lệ dependency lần này.

## Consequences

- `requirements.txt` thêm `openai`, `google-genai` (pin version chính xác lúc cài); giữ `anthropic==0.34.2`.
- `.env.example` thêm `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `LLM_PROVIDER_CHAIN`.
- `PrescribeResponse` (REST + gRPC) thêm field `llm_provider` — phục vụ trace provider nào sinh prescription, và làm input cho GH-24 (so sánh chất lượng per-provider).
- Core train/inference (`/predict`, `/health`) vẫn không phụ thuộc bất kỳ SDK nào trong số này.
- Tổng thời gian enrich bị giới hạn ~25s (mỗi tầng 10s/1 retry) để không treo event-driven call khi cả 2 provider đầu đều timeout trước khi rơi về rule-based.

## Alternatives đã cân nhắc

- **Giữ Anthropic single-provider (không đổi):** đơn giản nhất, nhưng không có backup khi Anthropic lỗi/hết quota — rơi thẳng rule-based dù có thể vẫn muốn LLM enrichment.
- **Chỉ đổi hẳn sang DeepSeek, bỏ Anthropic/không làm chain:** giảm phức tạp, nhưng lại quay về vấn đề single-point-of-failure như hiện tại, chỉ đổi provider.
- **Thêm retry/backoff dài thay vì fallback provider khác:** không giải quyết được trường hợp provider bị outage kéo dài; fallback sang provider khác thực tế hơn cho uptime.

## Cập nhật path (GH-96, 2026-07-10)

`src/services/llm/` (mô tả ở phần Decision) đã gom tiếp vào `src/services/prescription/llm/` cùng với `prescription.py` (→ `prescription/orchestrator.py`), `rule_prescription.py`, `safety_gate.py`, `rag_retriever.py` — tất cả nằm chung 1 subpackage `src/services/prescription/`. Kiến trúc chain/fallback không đổi, chỉ đổi vị trí file.
