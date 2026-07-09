# Plan — GH-79: [AI] Prescription — LLM provider layer: DeepSeek primary + Gemini fallback (thay Anthropic single-provider)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-09
- **Issue:** #79 — https://github.com/GSU26SE55/ai-module/issues/79
- **Sprint:** (chưa gán milestone)

## Mục tiêu
Thay `src/services/_llm_client.py` (hard-code Anthropic single-provider) bằng 1 provider chain có thể fallback: **DeepSeek (chính) → Gemini (backup) → rule-based (fallback cuối, không đổi)**. Anthropic vẫn giữ trong code như 1 provider tuỳ chọn trong chain (backward compat), không xoá. Output contract downstream (`prescription.py::_enrich`, `PrescribeResponse`) không đổi ngoài field mới `llm_provider`.

## Scope
**Trong scope:**
- Interface provider-agnostic (`LLMProvider`), 3 implementation: DeepSeek, Gemini, Anthropic (move từ code cũ, không đổi logic)
- Fallback chain cấu hình qua env `LLM_PROVIDER_CHAIN` (default `deepseek,gemini`)
- Field mới `llm_provider` trên `PrescribeResponse` (REST + gRPC parity)
- ADR ghi quyết định đổi provider + thêm dependency (`openai`, `google-genai`)
- Test mock cả 3 provider (không network trong CI) + test chain fallback từng tầng

**Ngoài scope:**
- Đổi prompt/system rules chống hallucination (giữ nguyên nội dung, chỉ tái dùng cho 3 provider)
- GH-24 (eval harness đo chất lượng per-provider) — issue riêng, làm sau khi #79 xong
- Đổi rule-based baseline (`rule_prescription.py`, `safety_gate.py`) — không đụng

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/llm/__init__.py` | create | package marker |
| `src/services/llm/base.py` | create | `LLMProvider` ABC: `is_available() -> bool`, `generate_prescription(context, maintenance_docs, safety_docs) -> dict{prescription, action_steps, ppe_required}` |
| `src/services/llm/anthropic_provider.py` | create | move nguyên logic hiện có trong `_llm_client.py` (forced tool-use, model `claude-haiku-4-5-20251001`) vào class `AnthropicProvider` — không đổi behavior |
| `src/services/llm/deepseek_provider.py` | create | `DeepSeekProvider` — SDK `openai`, `base_url=https://api.deepseek.com`, model `deepseek-chat` (env `DEEPSEEK_MODEL`), function calling ép structured output, cùng schema `emit_prescription` |
| `src/services/llm/gemini_provider.py` | create | `GeminiProvider` — SDK `google-genai`, model `gemini-2.5-flash` (env `GEMINI_MODEL`), `response_schema` |
| `src/services/llm/chain.py` | create | `is_available()`, `generate_prescription(...)` — duyệt `LLM_PROVIDER_CHAIN`, mỗi tầng timeout 10s/1 retry, tổng budget ~25s, trả thêm key `provider`; raise `RuntimeError` nếu tất cả fail/không có key nào (caller fallback rule-based như hiện tại) |
| `src/services/_llm_client.py` | delete | logic đã chuyển vào `llm/` |
| `src/services/prescription.py` | modify | import `from src.services.llm import chain` thay `_llm_client`; `_enrich()` set `llm_provider` từ `chain` result, mặc định `"none"` ở mọi nhánh fallback |
| `src/schemas/prescribe.py` | modify | `PrescribeResponse.llm_provider: str = "none"` |
| `protos/ai_service.proto` | modify | thêm `string llm_provider = 19;` vào `PrescribeResponse` (field number mới, không đổi field cũ) |
| `src/grpc_gen/*` | regenerate | `python scripts/gen_proto.py` |
| `src/grpc_server.py` | modify | `_to_prescribe_response()` map thêm `llm_provider` |
| `.env.example` | modify | thêm `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `LLM_PROVIDER_CHAIN` |
| `requirements.txt` | modify | thêm `openai==<pin>`, `google-genai==<pin>` (pin đúng version cài thực tế lúc implement); giữ `anthropic==0.34.2` |
| `docs/adr/0003-llm-provider-chain.md` | create | ADR — quyết định multi-provider chain, cite nối tiếp ADR-0001, ghi rõ user (full authority) đã duyệt dependency mới |
| `tests/test_llm_client.py` | delete | thay bằng `test_llm_providers.py` |
| `tests/test_llm_providers.py` | create | test từng provider (mock SDK, không network) + test chain: DeepSeek fail→Gemini nhận; cả 2 fail→RuntimeError; malformed output→nhảy tầng tiếp |
| `tests/test_prescription.py` | modify | đổi mock target `_llm_client` → `src.services.llm.chain`; assert `llm_provider` trong output cho từng case |
| `tests/test_grpc_server.py` | modify | thêm `llm_provider` vào list field parity (dòng ~588) |
| `tests/test_hybrid_prescription.py` | modify | **phát sinh ngoài plan ban đầu** — file này cũng import trực tiếp `_llm_client` (không nằm trong Files list gốc, bị sót lúc phân tích gap); vỡ ImportError sau khi xoá `_llm_client.py` ở Bước 3 → cập nhật mock target sang `chain`, giữ nguyên coverage cũ |

## Approach
- `base.py` định nghĩa contract giống hệt shape trả về hiện tại của `_llm_client.generate_prescription_llm()` — không đổi contract để `prescription.py` chỉ cần đổi import, không đổi logic union PPE / fallback.
- `AnthropicProvider` = di chuyển nguyên code cũ (đã test kỹ, forced tool-use) — zero behavior change, chỉ đổi vị trí.
- `DeepSeekProvider`/`GeminiProvider` implement cùng tool schema (`prescription`, `action_steps`, `ppe_required`) và cùng `_SYSTEM_PROMPT` chống hallucination như bản Anthropic hiện tại — tái dùng, không viết lại.
- `chain.py` là orchestrator duy nhất biết thứ tự provider; mỗi tầng thất bại (RuntimeError/timeout/malformed) → thử tầng tiếp, không retry chéo tầng; theo dõi tổng elapsed time để bounded ~25s.
- `prescription.py::_enrich()` giữ nguyên cấu trúc try/except hiện tại quanh lời gọi LLM — chỉ đổi tên module gọi và gán thêm `result["llm_provider"]`.

## Edge Cases
- Không có key nào trong chain + `enrich=true` → rule-based, `llm_provider="none"`, log info (như hiện tại)
- DeepSeek trả JSON thiếu field bắt buộc → coi là fail → thử Gemini
- Provider timeout giữa chừng → không retry chéo tầng vô hạn — mỗi provider tối đa 1 retry rồi nhảy tầng
- Rate-limit 429 → nhảy tầng ngay, không đợi retry-after
- Tổng thời gian enrich vượt ~25s → abort các tầng còn lại, fallback rule-based

## Acceptance Criteria
- [ ] `enrich=true` + có `DEEPSEEK_API_KEY` → prescription từ DeepSeek, `llm_provider="deepseek"`
- [ ] Giả lập DeepSeek lỗi → Gemini trả kết quả, `llm_provider="gemini"`
- [ ] Cả 2 lỗi/không key → rule-based, `enriched=false`, `llm_provider="none"`, HTTP 200 không crash
- [ ] Rule-path (`enrich=false`) benchmark <100ms, zero network — không regression so với `TestPrescriptionLatency` hiện có
- [ ] REST/gRPC parity field `llm_provider` (`test_prescribe_parity_with_rest`)
- [ ] Coverage ≥85% cho file mới trong `src/services/llm/`
- [ ] ADR `docs/adr/0003-llm-provider-chain.md` tồn tại

## Steps
- [x] Bước 1: `docs/adr/0003-llm-provider-chain.md` (ghi quyết định trước khi cài dependency) + `src/services/llm/base.py` — 2026-07-09
- [x] Bước 2: Cài `openai`, `google-genai`; pin version vào `requirements.txt` — 2026-07-09 (⚠️ google-genai kéo pydantic 2.7.4→2.13.4, đã verify không regression)
- [x] Bước 3: `anthropic_provider.py` — move logic từ `_llm_client.py`, xoá file cũ — 2026-07-09
- [x] Bước 4: `deepseek_provider.py` — OpenAI-compatible client + function calling — 2026-07-09
- [x] Bước 5: `gemini_provider.py` — google-genai client + response_schema — 2026-07-09
- [x] Bước 6: `chain.py` — fallback orchestrator + bounded timeout — 2026-07-09
- [x] Bước 7: `prescription.py` (import + `llm_provider`), `schemas/prescribe.py`, `.env.example` — 2026-07-09
- [x] Bước 8: `protos/ai_service.proto` field 19 → `python scripts/gen_proto.py` → `grpc_server.py` — 2026-07-09
- [x] Bước 9: `tests/test_llm_providers.py`, update `test_prescription.py`, `test_grpc_server.py` — 2026-07-09
- [x] Bước 10: Benchmark rule-path latency (không regression) + `pytest --cov=src --cov-report=term` ≥85% — 2026-07-09 (rule-path latency test PASS; coverage `src/services/llm/` = 100%, `prescription.py` = 99%, aggregate `src` = 90%; 321 tests PASS; `ruff check` sạch)

## Câu hỏi đã giải đáp
1. **Phạm vi "đổi sang DeepSeek"** — không chỉ dùng làm judge trong eval GH-24, mà đổi luôn provider chính production của Prescription Layer → đây chính là scope issue #79. Tạm gác GH-24, làm #79 trước (GH-24 phụ thuộc provider nào đang chạy thật).
2. **Cấu trúc file** — tách thành package `src/services/llm/` (base + 3 provider + chain), không nhồi vào 1 file `_llm_client.py` — vì có 3 provider + fallback chain + retry/timeout riêng từng tầng, dễ test và mở rộng provider sau này hơn.
