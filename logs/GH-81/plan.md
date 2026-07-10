# Plan — GH-81: Prescription — Safety gate v2: kiểm duyệt output LLM trước khi trả (blocked path + PPE/LOTO enforcement)

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-10
- **Branch:** `feat/GH-81-safety-gate-v2-output-validation`
- **Issue:** #81 — https://github.com/GSU26SE55/ai-module/issues/81
- **Sprint:** (chưa gán milestone) | **Priority:** P2 High | **Dev:** Nguyễn Phúc Duy (DuyNguyen-3006)

## Mục tiêu
Nâng cấp safety gate từ input-only lên **output validation**: kiểm duyệt `action_steps`/`ppe_required` do LLM sinh ra TRƯỚC khi trả về — inject LOTO/thermal step còn thiếu, union PPE bắt buộc theo PPE matrix, block hành động cấm (blocked path trả rule-based prescription), và LLM-as-judge optional sau rule validation. Expose field `blocked` ra contract (REST + gRPC).

## Scope
**Trong scope:**
- Rule-based output validation trong `safety_gate.py` (deterministic, không network)
- Blocked path trong orchestrator: swap sang rule-based + audit log
- LLM-as-judge qua provider chain GH-79, env flag `SAFETY_LLM_JUDGE` (default off)
- Contract: thêm `blocked` vào `PrescribeResponse` (REST) + proto field 20 + regen stub + parity test
- Test matrix theo acceptance criteria, coverage ≥ 85% file sửa

**Ngoài scope:**
- Không đổi rule_prescription templates / KB content (chỉ đọc, reuse constants)
- Không đổi provider chain order/budget logic của GH-79
- Không thêm anomaly type / model mới
- BE consume field `blocked` (việc của repo BE, chỉ cần proto sẵn)

## Endpoints
| Method | Path | Thay đổi |
|--------|------|----------|
| POST | `/prescribe/` | Response thêm `blocked: bool = false`. Blocked → vẫn HTTP 200, trả rule-based prescription |
| gRPC | `aimodule.v1.AiService/Prescribe` | `PrescribeResponse` thêm `bool blocked = 20` (field number mới, không reuse) |

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription/safety_gate.py` | modify | Core v2: PPE map theo `ppe_matrix.md`, LOTO/thermal inject, blocklist (negation-aware), signature mới — **pure function**, không side-effect |
| `src/services/prescription/orchestrator.py` | modify | Truyền output vào gate; blocked → swap rule-based + re-run enforcement; empty-steps fallback trong `_enrich`; audit log; wire judge |
| `src/services/prescription/llm/base.py` | modify | `JUDGE_SYSTEM_PROMPT` + `JUDGE_SCHEMA` (`{safe: bool, reason: str}`) + abstract `judge_safety()` |
| `src/services/prescription/llm/deepseek_provider.py` | modify | Impl `judge_safety` (mirror plumbing generate_prescription) |
| `src/services/prescription/llm/gemini_provider.py` | modify | Impl `judge_safety` |
| `src/services/prescription/llm/anthropic_provider.py` | modify | Impl `judge_safety` |
| `src/services/prescription/llm/chain.py` | modify | `judge_safety()` — cùng chain order + budget pattern |
| `src/schemas/prescribe.py` | modify | `blocked: bool = False` trong `PrescribeResponse` |
| `protos/ai_service.proto` | modify | `bool blocked = 20;` trong `PrescribeResponse` |
| `src/grpc_gen/ai_service_pb2.py` + `_grpc.py` | regen | `python scripts/gen_proto.py` — commit stub |
| `src/grpc_server.py` | modify | `_to_prescribe_response` map thêm `blocked` |
| `tests/test_rag_services.py` | modify | Test matrix gate v2 (unit, pure function) |
| `tests/test_prescription.py` | modify | Blocked path end-to-end + judge + audit log + latency |
| `tests/test_grpc_server.py` | modify | Parity field `blocked` |

## Approach

**1. Gate v2 — signature mở rộng, backward-compatible:**
```python
def apply_safety_gate(
    priority, action_code, warnings, prescription,
    action_steps: list[str] | None = None,   # None = v1 behavior (input-only)
    ppe_required: list[str] | None = None,
    llm_generated: bool = False,             # True → chạy blocklist
) -> dict:
    # returns thêm: blocked_reasons, matched_patterns,
    #               action_steps (đã inject), ppe_required (đã union)
```
Gate giữ **pure function** (không log, không network) — orchestrator chịu trách nhiệm audit log → dễ test, hot-path không đổi.

**2. Output validation (mọi path, kể cả rule-based):**
- Electrical critical (`VOLTAGE_CRITICAL`/`OVERVOLTAGE_CRITICAL`/`OVERCURRENT_CRITICAL`) mà steps không chứa `loto|lockout|tagout` → inject bước LOTO chuẩn (reuse text từ `rule_prescription.py` REPLACE_IMMEDIATELY step 1) vào **đầu** action_steps
- Thermal critical (`TEMP_CRITICAL`/fire/runaway/smoke) mà steps không chứa `evacuat|exclusion|ventilat|isolat` → inject step từ `_WARNING_STEPS["TEMP_CRITICAL"]` (thermal runaway SOP)
- PPE enforcement — map warning → PPE bắt buộc, grounded `knowledge/safety/ppe_matrix.md`: electrical critical → base + arc-flash + steel-toed; TEMP_ELEVATED → base + IR thermometer; thermal critical → KHÔNG thêm PPE (matrix: "no PPE substitutes for evacuation") mà inject evacuate step; REPLACE_IMMEDIATELY → base + steel-toed. Union bằng `_dedup` (mở rộng cơ chế union rule-PPE hiện có)

**3. Blocklist (chỉ khi `llm_generated=True`):** pattern cấm case-insensitive EN: mở/tháo/đâm thủng cell hoặc vỏ pin, đoản mạch test, dùng nước dập lửa lithium, thao tác vật lý khi đang sạc. Mỗi pattern kèm **negation guard** — step chứa `not|never|avoid|don't` trước match trong cùng step → KHÔNG tính vi phạm (tránh false positive trên "do NOT use water" vốn là text an toàn chuẩn). Match → `blocked=True` + `blocked_reasons` + `matched_patterns`.

**4. Blocked path (orchestrator):** `blocked=True` → audit log (logger `safety_gate.audit`, 1 record JSON: battery_id, priority, warning codes, output bị block, pattern khớp, nguồn block rule/judge) → swap `enriched` về `rule_out` (enriched=False, llm_provider="none", GIỮ docs đã retrieve — nhất quán fallback hiện tại) → **re-run gate 1 lần** trên rule output với `llm_generated=False` để rule output cũng được PPE/LOTO enforcement (không blocklist → không thể loop) → `human_verification_required=True`, `safety_warnings` ghi lý do.

**5. LLM-as-judge:** chạy SAU rule validation pass, CHỈ khi `enriched=True` và env `SAFETY_LLM_JUDGE` in `{"1","true"}` (default off). `chain.judge_safety(warnings_context, action_steps)` → `{safe, reason}`; unsafe → đi đúng blocked path như blocklist (đã chốt với user); mọi exception/timeout → pass (không block oan), log warning.

**6. Empty action_steps từ LLM:** xử lý trong `_enrich` — llm_out có `action_steps` rỗng → coi như provider failure, giữ rule-based (enriched=False). Không đưa vào gate.

## Edge Cases
- Rule-based path (enrich=False hoặc LLM fail): chỉ PPE/LOTO enforcement, **không blocklist** — rule text tự kiểm soát và có chứa "do NOT use water" hợp lệ
- Negation: "Do NOT use water on lithium fire" → pass; "Use water to extinguish" → block
- `action_steps` rỗng từ LLM → fallback rule-based ngay tại `_enrich`
- Gate v1 call sites (positional 4 args) vẫn chạy đúng nhờ default params — test cũ không vỡ
- Blocked → response vẫn HTTP 200 / gRPC OK (không phải error), `blocked=true` trong body
- Re-run gate sau swap không thể block lần 2 (blocklist tắt với rule output) → không vòng lặp
- Warning codes lạ/không map PPE → bỏ qua, không crash

## Acceptance Criteria
- [ ] Test matrix: (electrical critical / thermal critical / none) × (output thiếu LOTO / chứa hành động cấm / sạch) → inject / block / pass đúng từng ô (9 cells, unit test trên `apply_safety_gate`)
- [ ] `blocked=True` không bao giờ trả LLM output ra ngoài — orchestrator test mock chain trả banned steps → response chứa rule-based prescription, HTTP 200
- [ ] PPE union đúng theo ppe_matrix.md, không mất PPE nào của rule
- [ ] Judge: flag off → không gọi chain; flag on + unsafe → blocked; judge raise/timeout → pass
- [ ] Audit log kiểm tra được trong test (caplog: pattern khớp + output bị block)
- [ ] Hot-path rule-only không đổi latency < 100ms (gate = string matching thuần)
- [ ] gRPC/REST parity field `blocked` (test_grpc_server)
- [ ] Coverage ≥ 85% các file sửa; `ruff check` + `ruff format` sạch

## Steps
- [x] Bước 1 — Gate v2 core (`safety_gate.py`): PPE map + LOTO/thermal inject + blocklist negation-aware + signature/return mới — 2026-07-10
- [x] Bước 2 — Orchestrator: truyền output vào gate, blocked swap + re-run enforcement, empty-steps fallback, audit log — 2026-07-10
- [x] Bước 3 — Judge: base prompt/schema → 3 provider impl → `chain.judge_safety` → env flag wiring trong orchestrator — 2026-07-10
- [x] Bước 4 — Contract: `blocked` vào Pydantic schema + proto field 20 + `python scripts/gen_proto.py` + `_to_prescribe_response` — 2026-07-10
- [x] Bước 5 — Tests: unit matrix (test_rag_services) + orchestrator blocked/judge/audit (test_prescription) + parity (test_grpc_server) + REST blocked 200 (test_routers) + judge providers/chain (test_llm_providers) — 2026-07-10
- [x] Bước 6 — Verify: ruff check sạch (file sửa) + pytest 403 passed + coverage safety_gate 100% / orchestrator 99% / llm 97–100% + latency rule-path <100ms PASS — 2026-07-10

## Thay đổi so với plan gốc (minor — không đổi scope)
- Thêm 2 file test ngoài dự kiến: `tests/test_routers.py` (REST blocked → HTTP 200 end-to-end) và `tests/test_llm_providers.py` (judge per-provider + judge chain fallback, fake SDK) — phục vụ AC coverage ≥85% file sửa.
- `ruff format --check` bỏ qua có chủ ý: repo baseline vốn không format-clean (cả file không đụng tới cũng "would reformat") — chỉ enforce `ruff check` (pass). 8 lỗi ruff còn lại toàn repo là pre-existing ở file ngoài scope (grpc_gen stub, inference.py, test_confidence.py).
- Test fail duy nhất toàn suite: `test_kb_manifest` — pre-existing từ commit 32d0200 (KB files thêm mà manifest chưa update), fail cả trên tree sạch, KHÔNG liên quan GH-81.

## Câu hỏi đã giải đáp
1. **Expose `blocked` ra contract?** → **Có** — thêm `blocked: bool = False` vào PrescribeResponse + proto `bool blocked = 20` (field number mới). BE (gRPC production transport) nhận signal tường minh; issue yêu cầu ghi rõ quyết định này.
2. **Judge verdict unsafe → làm gì?** → **Block như blocklist** — đi chung 1 blocked path (rule-based fallback + human_verification_required + audit log). Block oan đã được chặn bởi "judge fail/timeout → pass" + flag default off.
3. **Path file trong issue** (`src/services/safety_gate.py`) thực tế là `src/services/prescription/safety_gate.py` — issue viết tắt, không có file thứ hai.
