# Plan — GH-96: [AI] Refactor — gom prescription/RAG/LLM vào subpackage src/services/prescription/

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-10
- **Issue:** #96 — https://github.com/GSU26SE55/ai-module/issues/96
- **Sprint:** (chưa gán milestone)

## Mục tiêu
Gom 5 module rải phẳng trong `src/services/` (prescription/rule_prescription/safety_gate/rag_retriever/llm) vào 1 subpackage `src/services/prescription/`, chuẩn bị chỗ rõ ràng trước khi làm #81/#83/#84. **Không đổi behavior** — thuần di chuyển file + sửa import path.

## Scope
**Trong scope:** di chuyển 5 module + `llm/` subpackage, sửa import nội bộ, sửa test patch target, giữ public API `from src.services.prescription import run_prescription` không đổi cho `routers/prescribe.py` và `grpc_server.py`, cập nhật path-depth trong `rag_retriever.py`, cập nhật docs tham chiếu path cũ.

**Ngoài scope:** đổi logic/behavior bất kỳ hàm nào, làm #81/#83/#84.

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription/__init__.py` | create | `from src.services.prescription.orchestrator import run_prescription` — public API duy nhất |
| `src/services/prescription/orchestrator.py` | create (move) | nội dung y hệt `src/services/prescription.py` cũ, sửa import: `rule_prescription`/`safety_gate` cùng cấp, `rag_retriever`/`llm` lazy-import trỏ path mới |
| `src/services/prescription/rule_prescription.py` | create (move) | y hệt nội dung cũ |
| `src/services/prescription/safety_gate.py` | create (move) | y hệt nội dung cũ |
| `src/services/prescription/rag_retriever.py` | create (move) | y hệt nội dung cũ, path-depth `os.path.dirname` thêm 1 lớp (sâu hơn 1 cấp) |
| `src/services/prescription/llm/*.py` | create (move) | y hệt nội dung cũ, sửa import nội bộ `src.services.llm.X` → `src.services.prescription.llm.X` |
| `src/services/prescription.py` | delete | đã move |
| `src/services/rule_prescription.py` | delete | đã move |
| `src/services/safety_gate.py` | delete | đã move |
| `src/services/rag_retriever.py` | delete | đã move |
| `src/services/llm/` | delete | đã move |
| `src/routers/prescribe.py`, `src/grpc_server.py` | không đổi | public API path giữ nguyên |
| `tests/test_prescription.py` | modify | `from src.services import prescription` → `from src.services.prescription import orchestrator as prescription` (giữ nguyên toàn bộ `patch.object(prescription, ...)` phía dưới) |
| `tests/test_hybrid_prescription.py` | modify | sửa 3 import path (`llm`, `prescription` → `.orchestrator`, `rule_prescription`) |
| `tests/test_llm_providers.py` | modify | sửa import `src.services.llm.*` → `src.services.prescription.llm.*` |
| `tests/test_rag_services.py` | modify | sửa import `rag_retriever`/`safety_gate` |
| `tests/test_grpc_server.py` | không đổi | patch target (`src.grpc_server.run_prescription`, `src.routers.prescribe.run_prescription`) không phụ thuộc path nội bộ |
| `docs/adr/0001-rag-llm-dependency-exception.md`, `docs/adr/0003-llm-provider-chain.md`, `docs/prescription-layer.md` | modify | sửa path liệt kê cho đúng |

## Approach
- **Không sửa nội dung logic** — mỗi file move nguyên xi, chỉ đổi các dòng `import`.
- `__init__.py` chỉ export `run_prescription` — đây là điều duy nhất `routers/prescribe.py` và `grpc_server.py` cần, nên 2 file đó không phải sửa gì.
- Test patch target: mock hoạt động bằng cách patch đúng module nơi tên được *lookup lúc gọi*, không phải nơi định nghĩa gốc — vì vậy `tests/test_prescription.py` phải trỏ sang `orchestrator` (module thật chứa lệnh gọi `run_inference(...)`, `chain.generate_prescription(...)`), không thể patch qua `__init__.py` (package namespace) vì patch đó sẽ không có tác dụng lên lời gọi bên trong `orchestrator.py`.
- `rag_retriever.py` sâu thêm 1 cấp thư mục → `KNOWLEDGE_DIR`/`EMBEDDINGS_DIR` cần thêm 1 `os.path.dirname(...)`.

## Edge Cases
- `models/embeddings/`, `knowledge/` không đổi vị trí — chỉ code Python di chuyển, không đụng data.
- `scripts/ingest_rag.py` không import từ `src/services/` — không bị ảnh hưởng.

## Acceptance Criteria
- [ ] `src/routers/prescribe.py`, `src/grpc_server.py` không có diff
- [ ] `pytest tests/ -q --cov=src` toàn bộ PASS, coverage không giảm so với hiện tại (90%)
- [ ] `ruff check` sạch
- [ ] Docs (ADR-0001, ADR-0003, prescription-layer.md) hết reference path cũ

## Steps
- [x] Bước 1: Tạo `src/services/prescription/` — move 4 file (orchestrator, rule_prescription, safety_gate, rag_retriever) + `llm/`, sửa import nội bộ + path-depth — 2026-07-10 (dùng `git mv` giữ history)
- [x] Bước 2: Tạo `__init__.py`, xoá 5 đường dẫn cũ — 2026-07-10 (git mv đã tự rename, `src/services/` giờ chỉ còn `battery_history.py`, `confidence.py`, `inference.py`, `prescription/`)
- [x] Bước 3: Sửa 4 file test (`test_prescription.py`, `test_hybrid_prescription.py`, `test_llm_providers.py`, `test_rag_services.py`) — 2026-07-10 (phát hiện thêm 5 string-literal patch target `"src.services.llm.chain..."` trong `test_prescription.py` mà lúc phân tích ban đầu bỏ sót — đã sửa bằng sed)
- [x] Bước 4: Sửa docs tham chiếu path cũ — 2026-07-10 (ADR-0001/0003: giữ nguyên nội dung lịch sử, thêm mục "Cập nhật path (GH-96)"; `prescription-layer.md`: thêm ghi chú inline vì đoạn đó mô tả state lịch sử của branch cũ)
- [x] Bước 5: `pytest tests/ -q --cov=src` + `ruff check` — verify không regression — 2026-07-10 (347/347 PASS, coverage aggregate 90% giữ nguyên, `ruff check` sạch — fix thêm 1 unused import pre-existing trong `test_rag_services.py`; `src/routers/prescribe.py` và `src/grpc_server.py` xác nhận 0 diff qua `git status`)

## Câu hỏi đã giải đáp
Không có — toàn bộ approach đã thống nhất qua trao đổi trong phiên làm việc (gom subpackage, giữ public API `run_prescription` không đổi, patch target theo `orchestrator.py`).
