# ADR 0004 — Long-term memory store cho Prescription Layer (GH-83)

- **Status:** Accepted
- **Ngày:** 2026-07-14
- **Liên quan:** GH-83 (long-term memory + feedback loop), GH-80 (KB tĩnh), GH-79 (provider chain), GH-81 (safety gate v2), GH-82 (agentic chain)
- **Context rule:** `.claude/rules/tech/ai.md` — inference latency P1 `<100ms`; ADR 0001/0003 (ngoại lệ dependency prescription layer)

## Context

Paper Deng et al. 2024 (Future Work — "From Ad-hoc Prompting to Long-Term Memory") chỉ ra: mỗi lần generate, agent nạp lại từ đầu, không tham chiếu được các chẩn đoán/prescription trước đó. GH-83 thêm khả năng lưu prescription đã trả + feedback của technician, dùng case đã được xác nhận (`accepted`) làm few-shot context cho lần enrich sau. Điều này đặt ra 4 câu hỏi kiến trúc cần quyết định trước khi implement (không có trong issue gốc, phải làm rõ với người phụ trách trước khi code):

## Decision

### 1. Store riêng, KHÔNG dùng chung `models/embeddings/`

`models/embeddings/chroma.sqlite3` (GH-80) là **KB tĩnh, committed vào Git**, kiểm tra bởi `test_kb_manifest` — tái lập được, không đổi ngoài lúc re-ingest có chủ đích. Lịch sử prescription là **dữ liệu runtime tích luỹ liên tục** (mỗi lần `/prescribe` enrich=true) — ghi vào cùng file sẽ làm dirty artifact đã commit mỗi lần chạy server/test.

→ `PrescriptionHistoryStore` dùng `PersistentClient` **riêng** tại `models/prescription_history/`, thêm vào `.gitignore` — không commit, không kiểm tra bởi manifest.

### 2. Chỉ ghi history khi `enrich=true`

`ai.md` yêu cầu P1 hot-path (`enrich=false`) `<100ms`, hiện tại "never touches the network". Ghi ChromaDB (encode embedding qua sentence-transformer + `collection.add`) tốn thêm compute không nhỏ — không được phép trên rule-only path.

→ `run_prescription()` chỉ gọi `history_store.save()` khi `enrich=True`; `enrich=false` trả `prescription_id=""`, không có record, không có write nào xảy ra (test `test_history_not_touched_when_enrich_false` enforce bằng cách raise nếu `_get_history_store()` bị gọi).

### 3. FIFO cap N=500

Không giới hạn kích thước → embeddings phình vô hạn theo thời gian vận hành. N=500 (hằng số code, không qua `.env` — nhất quán cách `CONTAMINATION`/`N_ESTIMATORS` là hằng số, không phải config runtime) đủ cho vài tháng vận hành scope capstone. Evict theo `timestamp` cũ nhất khi vượt cap, chạy trong `save()` sau mỗi write thành công (best-effort, không raise nếu evict lỗi).

### 4. Feedback endpoint REST-only, không thêm RPC gRPC

`POST /prescribe/feedback` không nằm trên hot-path, tần suất thấp (≈1 lần/ticket CLOSED) — không cần gRPC cho use-case này trong scope GH-83. Field `prescription_id` mới trên `PrescribeResponse` (RPC `Prescribe` đã có sẵn) **vẫn cần parity REST/gRPC** vì đó là field của response type đã tồn tại — proto field 23, `grpc_server.py` cập nhật, `test_grpc_server.py` parity test mở rộng.

## Consequences

- `src/services/prescription/history_store.py` — `PrescriptionHistoryStore`, cùng optional-dependency pattern (`chromadb`/`sentence-transformers`, lazy import, `_ready=False` graceful) như `rag_retriever.py` (ADR 0001). Constructor bắt **mọi** exception khi import/khởi tạo (không chỉ `ImportError`) — môi trường có thể raise lỗi khác (đã gặp: `RuntimeError` từ chromadb's home-directory detection) mà vẫn phải degrade an toàn, không crash pipeline.
- `SYSTEM_PROMPT` (dùng chung 3 provider) thêm rule: past cases chỉ tham khảo, ưu tiên retrieved SOP docs khi mâu thuẫn — tránh self-reinforcing sai nếu 1 case cũ có vấn đề nhưng lọt qua feedback.
- Chỉ case `feedback_status="accepted"` được retrieve làm context — `pending`/`edited`/`rejected` bị loại (lọc bằng ChromaDB `where` filter), tránh khuếch đại prescription chưa được xác nhận hoặc đã bị sửa/từ chối.
- History lưu **nội dung cuối cùng đã trả cho caller** (sau block-path xử lý ở `run_prescription()`, không phải trong `_enrich()`) — nếu LLM output bị chặn bởi safety gate (GH-81), record lưu là bản rule-based, không phải bản đã bị chặn.
- `docs/prescription-feedback-contract.md` — contract cho BE gọi feedback khi ticket CLOSED (map maintenance log outcome → `accepted`/`edited`/`rejected`).

## Alternatives đã cân nhắc

- **Dùng chung `models/embeddings/`** (đúng như issue mô tả ban đầu): đơn giản hơn (1 client, 1 path) nhưng phá bất biến "KB tĩnh, tái lập được" của GH-80 — loại bỏ.
- **Ghi history cho cả `enrich=false`** (khớp nghĩa đen "mỗi lần /prescribe thành công" trong issue): vi phạm AC "rule-path không đổi latency"; có thể làm async/fire-and-forget nhưng tăng phức tạp không cần thiết cho scope capstone — loại bỏ, chỉ ghi khi `enrich=true`.
- **Không giới hạn kích thước:** đơn giản nhất nhưng không bền vững lâu dài — chọn FIFO N=500 làm cận trên rõ ràng, dễ giải thích khi bảo vệ.
- **Thêm RPC gRPC cho feedback ngay:** đối xứng hơn với các RPC khác nhưng use-case tần suất thấp, không cần thiết trong scope GH-83 — để lại cho issue sau nếu BE thực sự cần.
