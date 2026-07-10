## BÁO CÁO CODE REVIEW — feat/GH-80-expand-kb-ingest-v2 — 2026-07-10
### Scope: AI
### Effort: Standard

> **Lưu ý phạm vi:** Branch này gộp cả **GH-80** (mở rộng KB + ingest pipeline v2) và **GH-96** (refactor gom `src/services/{prescription,rule_prescription,rag_retriever,safety_gate,llm}` vào subpackage `src/services/prescription/`) — vì làm liên tiếp trong cùng working tree, chưa commit. Review này bao phủ cả 2. `docs/nckh/section4-experiments-vi.md` và các file trong `logs/nckh/`, `notebooks/kaggle_train_ablation.ipynb` là WIP của người dùng khác (không thuộc 2 issue này) — loại khỏi phạm vi review.

### TÓM TẮT
Diff gồm 2 phần: (1) KB mở rộng 4→13 doc + `ingest_rag.py` v2 (heading-aware chunk, manifest, idempotent) — logic đã verify bằng chạy thật 2 lần (39+25=64 chunk ổn định); (2) refactor thuần di chuyển file, đã verify `src/routers/prescribe.py`/`src/grpc_server.py` 0 diff. Không phát hiện lỗi Critical. Có 1 gap về test coverage đáng lưu ý.

### PHÂN TÍCH

🟡 **Warning: `scripts/ingest_rag.py` — logic chunking mới (`chunk_by_section`, `_fallback_chunk`, `_delete_by_source`, `_existing_sources`) không có unit test riêng trong `tests/`.**
Toàn bộ verify hiện tại là chạy script thật 2 lần thủ công (ghi trong `logs/GH-80/plan.md` Bước 4) — không phải test tự động trong `pytest tests/`. Dự án đã có tiền lệ unit-test file trong `scripts/` (`tests/test_preprocess.py` test `scripts/preprocess.py`), nên đây là khoảng trống thực sự, không phải quá mức yêu cầu. Rủi ro cụ thể: nếu sau này ai sửa `MAX_SECTION_SIZE`/regex heading hoặc thêm doc không có `##` nào (rơi vào nhánh fallback `if not matches:` — nhánh này **chưa từng được exercise** vì cả 13 doc hiện tại đều có H2), không có gì báo động nếu logic đó silently sai.
→ Gợi ý: thêm `tests/test_ingest_rag.py` test trực tiếp `chunk_by_section()` với 1 case không có H2 heading + 1 case section > `MAX_SECTION_SIZE` (exercise nhánh fallback), không bắt buộc phải chạy full script với chromadb thật.

✅ **Pass: Idempotency đã verify bằng chạy thật, không chỉ mock.** `_delete_by_source` (xoá theo `source` trước khi upsert) + so sánh `collection.count()` giữa 2 lần chạy — cách verify đúng, không phải "chạy 1 lần rồi giả định".

✅ **Pass: Regex heading-detection đúng, không có H2/H3 collision.** `_H2_RE = r"^##\s+(.+)$"` không match `### Subheading` (yêu cầu `\s` ngay sau đúng 2 ký tự `#`, `###` có ký tự `#` thứ 3 nên fail tại vị trí `^`, MULTILINE không cho retry giữa dòng) — verify bằng đọc kỹ regex, không phải test trực tiếp (liên quan đến Warning ở trên).

✅ **Pass: `rag_retriever.py` path-depth đúng sau khi move sâu thêm 1 cấp** — đã tự verify bằng script Python độc lập (`os.path.dirname` × 4 → đúng repo root), không chỉ dựa vào test pass.

✅ **Pass: Refactor GH-96 không đổi public API.** `src/services/prescription/__init__.py` chỉ export `run_prescription`; `git status` xác nhận `src/routers/prescribe.py` và `src/grpc_server.py` 0 diff — đúng yêu cầu acceptance criteria.

✅ **Pass: Test patch target sau refactor đúng nguyên tắc mock.** `tests/test_prescription.py` đổi sang `from src.services.prescription import orchestrator as prescription` (patch đúng module nơi tên được lookup lúc gọi — không patch qua `__init__.py` package namespace, tránh lỗi patch-không-có-tác-dụng kinh điển). Đồng thời tự phát hiện và sửa 5 string-literal patch target (`"src.services.llm.chain..."`) bị sót ở phân tích ban đầu.

✅ **Pass: Citation cho nội dung KB mới.** Cả 9 doc mới đều có mục `## References` trích từ bảng đã có sẵn trong `.claude/docs/ai-research-references.md` B2 §1 — không tự đặt threshold/standard mới, đúng approach đã thống nhất với user (Claude draft, user tự review kỹ thuật trước bảo vệ — đã note rõ trong plan.md).

✅ **Pass: `requirements.txt`/dependency — không có thay đổi trong diff này** (GH-80/GH-96 không thêm dependency mới, chỉ GH-79 trước đó đã xử lý).

### Checklist AI — các mục N/A cho diff này
- Reproducibility/Data/Model/FastAPI Endpoint (theo `.claude/skills/dev/ai/code-review/SKILL.md`) phần lớn N/A — diff này không train model, không đổi input schema Mamba/IsolationForest, không đổi endpoint. Random seed N/A vì không có thành phần stochastic (sentence-transformer encode là deterministic, đã verify qua 2 lần chạy cho cùng kết quả).

### RỦI RO & LƯU Ý
- Branch gộp 2 issue (GH-80 + GH-96) — cần quyết định ship chung 1 PR hay tách trước khi chạy `/kltn-ship`.
- `models/embeddings/` (bao gồm `manifest.json` mới) chưa commit — acceptance criteria GH-80 yêu cầu commit cùng 1 commit với `knowledge/`, nhắc lúc `/kltn-ship`.
- GH-79 đã nằm sẵn trong `dev` (không qua PR — xem lịch sử commit `b4236b0`/`149f3de`) nên không xuất hiện trong diff này; không phải lỗi của review này nhưng đáng note cho hồ sơ.

### KẾT LUẬN
**PASS** — Độ tự tin: Cao. Không có Critical. 1 Warning (thiếu unit test cho `chunk_by_section`) không chặn ship — khuyến nghị thêm trước khi coi GH-80 là "Done" hoàn toàn, nhưng không bắt buộc phải fix ngay trong review này.
