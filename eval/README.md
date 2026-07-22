# Prescription Evaluation Harness (GH-24)

Đo chất lượng lớp RAG/LLM của Prescription Layer — trả lời câu hỏi "RAG có ích không, dựa trên đâu?" cho hồ sơ bảo vệ KLTN.

## Chạy

```bash
python scripts/ingest_rag.py          # 1 lần, build vector store (nếu chưa có)
python eval/evaluate_prescription.py  # chạy full golden set, 3 nhánh
python eval/evaluate_prescription.py --output-dir logs/eval  # (mặc định)
```

Cần `chromadb` + `sentence-transformers` (đã pin trong `requirements.txt`). Để có số liệu **faithfulness** và text LLM thật cho 2 nhánh hybrid, cần 1 LLM key trong `.env` (ví dụ `DEEPSEEK_API_KEY=...`, theo `LLM_PROVIDER_CHAIN` — xem `docs/adr/0003-llm-provider-chain.md`). Không có key: coverage + SOP-overlap vẫn chạy đúng (không cần mạng), faithfulness trả `N/A`.

Output: `logs/eval/results.json` (raw per-scenario) + `logs/eval/report.md` (bảng summary, cùng convention với `scripts/eval_anomaly.py`).

## Golden set

`tests/fixtures/rag_golden_set.json` — 14 kịch bản hand-labeled (tạo từ GH-82, tái dùng nguyên cho GH-24), mỗi kịch bản gồm:
- `prediction`/`anomaly`/`risk`/`warnings` — đúng shape `run_inference()` trả về (**không phải raw sensor readings**)
- `expected_sources` — danh sách file `knowledge/{maintenance,safety}/*.md` mà 1 chuyên gia domain xác nhận là tài liệu đúng cho kịch bản đó

Phủ đủ 4 `action_code` chính: `MONITOR`, `SCHEDULE_MAINTENANCE`, `SCHEDULE_REPLACEMENT`, `REPLACE_IMMEDIATELY`.

## 3 nhánh (arms)

Mỗi kịch bản chạy qua `run_prescription()` **thật** (không tái tạo logic riêng) với `run_inference()` bị mock để trả thẳng `prediction`/`anomaly`/`risk`/`warnings` của kịch bản — bỏ qua model SOH/anomaly thật (đó là việc của GH-70), giữ kết quả **reproducible** (MC Dropout sampling sẽ khiến mỗi lần chạy model thật ra số khác nhau).

| Nhánh | `enrich` | `agentic` | Mô tả |
|-------|----------|-----------|-------|
| `rule` | `False` | — | Rule engine tĩnh, không RAG/LLM (luôn <100ms) |
| `hybrid_template` | `True` | `False` | RAG template query (GH-20/22) + LLM sinh prescription |
| `hybrid_agentic` | `True` | `True` | LLM tự sinh 3-5 query từ diagnosis statement (GH-82) trước khi retrieve |

## Metric

### Coverage (retrieval recall@k)
```
coverage = |expected_sources ∩ retrieved_sources| / |expected_sources|
```
Chỉ tính cho 2 nhánh hybrid (`rule` không bao giờ retrieve). Không cần LLM key — retrieval là bước độc lập, chạy trước bước sinh text.

### SOP overlap
```
sop_overlap = |{s ∈ expected_sources : basename(s) xuất hiện trong sop_references}| / |expected_sources|
```
`sop_references` của rule engine là tên người-đọc-được kèm mục lục (vd `"battery_maintenance_sop §3 (Replacement Criteria)"`), không phải file path — nên so bằng substring match trên basename (`battery_maintenance_sop`), không phải set equality.

**Chỉ tính 1 lần/kịch bản, không phải 1 lần/nhánh** — `sop_references` do rule engine sinh từ `action_code` duy nhất, `enrich`/`agentic` không hề chỉnh sửa field này (xem `orchestrator.run_prescription()`: `"sop_references": rule_out["sop_references"]` không đổi qua các nhánh). Báo cáo ablation ghi SOP overlap ở cột `rule`, 2 cột hybrid đánh dấu `—` (không phải N/A — giá trị giống hệt, không phải "không đo được").

### Faithfulness
```
faithfulness = max_i cosine_similarity(embed(generated_text), embed(retrieved_doc_i.content))
```
`generated_text` = `prescription` + các `action_steps` nối lại. `embed()` dùng `SentenceTransformer("all-MiniLM-L6-v2")` — **đúng model** `RagRetriever` đang dùng cho retrieval (tái dùng, không tải thêm model). Đo "có ít nhất 1 doc được retrieve thật sự support câu này không" — không so với text kỳ vọng nào (faithfulness kiểu RAG chuẩn không cần gold answer, chỉ cần context đã retrieve).

**Chỉ tính khi `enriched == True`** — tức là có LLM key, LLM gọi thành công, và safety gate không block output. Không có key hoặc bị block → `None` ("N/A" trong báo cáo), không phải `0.0` — tránh hiểu nhầm "faithfulness thấp" khi thực ra "chưa đo được".

## Ablation

Bảng so sánh 3 nhánh trên cùng golden set — trả lời trực tiếp câu hỏi "hybrid có tốt hơn rule không" và "agentic có tốt hơn template không" (câu thứ 2 GH-82 chưa từng có số liệu chính thức, GH-24 bổ sung luôn).

## Giới hạn đã biết

- **Reproducibility có giới hạn ở phần text LLM sinh ra**: coverage và SOP-overlap 100% reproducible (deterministic, embedding retrieval + rule engine không có randomness). Faithfulness thì công thức tính similarity là deterministic, nhưng **text đầu vào** (do LLM sinh) không reproducible tuyệt đối giữa các lần chạy — provider hiện tại (`llm/{deepseek,gemini,anthropic}_provider.py`) không expose tham số `temperature=0`/seed. Điểm số faithfulness vì vậy có thể dao động nhẹ giữa các lần chạy live, dù công thức đo và golden set đều cố định.
- **Không có LLM key → agentic tự động fallback về template**: `chain.generate_queries()` thất bại khi không có key → orchestrator rơi về template query (đúng thiết kế orchestrator, không phải bug harness). Khi đó `hybrid_agentic` và `hybrid_template` cho **số coverage giống hệt nhau** — đây là tín hiệu "không có key", không phải "agentic vô dụng". Xem dòng `LLM-enriched: N/14` đầu báo cáo để biết có key hay không trước khi diễn giải số liệu.
- **14 kịch bản là golden set nhỏ** (đủ AC ≥10, đủ phủ 4 action_code) — không đủ lớn để tách CI theo nhiễu thống kê (không báo confidence interval). Diễn giải số liệu ở mức "xu hướng", không phải "significance test".
- **Faithfulness không so với ground-truth text** — chỉ đo độ "bám" vào tài liệu đã retrieve, không đo "câu trả lời có đúng về mặt domain expert" (đó cần review thủ công hoặc LLM-as-judge, đã cân nhắc và loại vì tốn chi phí + không reproducible — xem `logs/GH-24/plan.md` mục "Câu hỏi đã giải đáp").
