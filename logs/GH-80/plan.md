# Plan — GH-80: [AI] Prescription — Mở rộng Knowledge Base + chuẩn hoá ingest pipeline

## Metadata
- **Status:** REVIEWING | **Role:** AI | **Ngày:** 2026-07-10
- **Issue:** #80 — https://github.com/GSU26SE55/ai-module/issues/80
- **Sprint:** (chưa gán milestone)

## Mục tiêu
Mở rộng Knowledge Base cho Prescription Layer từ 4 → ≥12 document (SOP theo action_code, 15 AnomalyType, 12V/LiFePO4, solar-specific, PPE matrix — mỗi doc có citation), và viết lại `scripts/ingest_rag.py` (v2): chunk theo section markdown (heading-aware) thay vì cắt cứng 512 ký tự, metadata đủ 5 field, `manifest.json` để test CI phát hiện `knowledge/` ↔ `models/embeddings/` lệch nhau, ingest idempotent.

## Scope
**Trong scope:**
- 9 file KB mới (xem Files), giữ nguyên 4 file hiện có
- `ingest_rag.py` v2: heading-aware chunking + fallback cắt dài + metadata 5 field + manifest.json + xoá chunk mồ côi khi file bị xoá/đổi tên
- Test CI: hash `knowledge/*.md` so với `manifest.json`
- Retrieval smoke test thủ công, ghi kết quả vào issue
- Regenerate `models/embeddings/`, commit cùng 1 commit với `knowledge/`

**Ngoài scope:**
- Đổi embedding model (`all-MiniLM-L6-v2`) hoặc thêm reranker
- Query generation bằng LLM (issue #82 riêng)
- Đổi `RetrievedDoc` schema / `rag_retriever.py` API (title/content/source/relevance_score giữ nguyên — field mới chỉ nằm trong metadata lúc ingest, không cần trả về qua retrieval API)
- Sửa `rule_prescription.py` để dùng warning code mới — KB chỉ là tài liệu tham khảo cho LLM enrich, không bắt buộc khớp 1:1 với 12 warning code hiện có của rule engine (rule engine dùng bộ hẹp hơn dựa trên V/I/T; KB phủ rộng hơn theo 15 AnomalyType phía BE để LLM có ngữ cảnh khi BE tích hợp GH-23 sau này)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `knowledge/maintenance/action_code_sop.md` | create | 4 section: MONITOR / SCHEDULE_MAINTENANCE / SCHEDULE_REPLACEMENT / REPLACE_IMMEDIATELY — đối chiếu template hiện có trong `rule_prescription.py` |
| `knowledge/maintenance/anomaly_electrical.md` | create | 6 type: Overvoltage, Undervoltage, RapidDischarge, AbnormalCharging, HighInternalResistance, CellImbalance |
| `knowledge/safety/anomaly_thermal.md` | create | 2 type: Overheat, HighAmbientTemp |
| `knowledge/maintenance/anomaly_soc_soh.md` | create | 2 type: LowSoc, SohDegradation |
| `knowledge/safety/anomaly_environmental.md` | create | 3 type: HighHumidity, HighTempHumidityCombo, EnvironmentalIncident |
| `knowledge/maintenance/anomaly_connectivity.md` | create | 2 type: DeviceOffline, SensorMismatch |
| `knowledge/maintenance/battery_12v_lifepo4.md` | create | 12V pack + LiFePO4 — per-cell voltage, `n_series` normalization (GH-65/67), chemistry threshold khác NMC |
| `knowledge/maintenance/solar_operations.md` | create | sạc/xả theo chu kỳ ngày, ảnh hưởng nhiệt độ môi trường, kiểm tra định kỳ theo mùa |
| `knowledge/safety/ppe_matrix.md` | create | PPE theo mức cảnh báo (electrical/thermal × warning/critical) |
| `scripts/ingest_rag.py` | modify | v2: heading-aware chunk + fallback, metadata 5 field, manifest.json, xoá chunk mồ côi |
| `models/embeddings/manifest.json` | create (generated) | hash + số chunk + ngày ingest, per file |
| `models/embeddings/` | regenerate | re-run ingest, commit cùng commit với `knowledge/` |
| `tests/test_kb_manifest.py` | create | hash `knowledge/*.md` so với `manifest.json` — FAIL nếu lệch/thiếu/thừa entry |

## Approach
- **Nguồn tin cậy cho nội dung mới:** dùng đúng bảng citation đã có sẵn trong `.claude/docs/ai-research-references.md` Phụ lục B2 §1 (threshold + reference cho từng AnomalyType) — không tự đặt threshold/standard mới. Nội dung symptoms/causes/response-steps viết bảo thủ theo domain knowledge Li-ion phổ thông, cùng format với 4 doc hiện có (`# Title` → `## Section` → bullet/table → `## References`).
- **Chunking v2:** parse theo heading `##` (H2) — mỗi section = 1 chunk nếu ≤ `MAX_SECTION_SIZE` (giả định 1500 ký tự, lớn hơn ngưỡng cũ 512 vì heading-aware giữ nguyên bảng/danh sách); section vượt ngưỡng mới rơi về sliding-window cũ (512/64) làm fallback.
- **Metadata 5 field:** `title` (như cũ), `source` (như cũ), `section` (tên heading H2 của chunk), `doc_version` (sha256 rút gọn của nội dung file — đổi tự động khi file đổi, không cần bookkeeping thủ công), `ingested_at` (ISO timestamp lúc chạy ingest).
- **Idempotent:** trước khi ingest 1 file, xoá toàn bộ chunk cũ có `source` trùng (`collection.get(where={"source": ...})` → `collection.delete(ids=...)`) rồi upsert lại — chạy lại nhiều lần cho cùng nội dung ra cùng số chunk. Sau khi ingest hết file hiện có, so `source` distinct trong collection với danh sách file hiện tại trong `knowledge/` → xoá chunk của file không còn tồn tại (xử lý case xoá/đổi tên).
- **Manifest + test CI:** `manifest.json` ghi `{sha256, chunks, ingested_at}` theo từng file lúc `ingest_rag.py` chạy xong; `test_kb_manifest.py` tính lại sha256 hiện tại của mọi file `knowledge/*.md` và so với manifest — phát hiện ngay nếu ai sửa `knowledge/` mà quên re-ingest.
- Không đổi `rag_retriever.py`/`RetrievedDoc` — field mới chỉ ở tầng ingest/manifest, API retrieval giữ nguyên contract cũ.

## Edge Cases
- File `knowledge/*.md` bị xoá sau khi đã ingest → chunk mồ côi bị xoá ở lần ingest tiếp theo (không rác vĩnh viễn trong vector store)
- File đổi tên → coi như file cũ bị xoá + file mới được thêm (source khác nhau, không tự động "rename-aware")
- Section markdown dài hơn `MAX_SECTION_SIZE` (vd bảng dài) → fallback sliding-window, không throw lỗi
- Chạy `ingest_rag.py` khi thiếu `chromadb`/`sentence-transformers` → giữ hành vi cũ (print hướng dẫn cài, không crash)
- `test_kb_manifest.py` chạy khi chưa từng ingest (`manifest.json` không tồn tại) → FAIL rõ ràng, nhắc chạy `ingest_rag.py`

## Acceptance Criteria
- [ ] KB ≥ 12 documents có nguồn cite, phủ đủ 4 action_code + 15 anomaly type + 12V/LiFePO4
- [ ] Chunk theo section, metadata đủ 5 field; `manifest.json` + `test_kb_manifest.py` PASS
- [ ] Chạy `ingest_rag.py` 2 lần liên tiếp → số chunk không đổi (idempotent) — verify thủ công, ghi vào issue
- [ ] Retrieval smoke test: query từng action_code/warning code chính → top-3 có doc đúng chủ đề — ghi kết quả vào issue (baseline cho GH-24)
- [ ] `models/embeddings/` commit cùng 1 commit với `knowledge/` thay đổi
- [ ] `pytest tests/ -q` toàn bộ PASS (không regression `test_rag_services.py`, `test_prescription.py`)

## Steps
- [x] Bước 1: Viết 9 file KB mới (nội dung + citation từ B2 §1) — 2026-07-09 (tổng 13 doc, ≥12)
- [x] Bước 2: Viết lại `scripts/ingest_rag.py` v2 (heading-aware chunk, metadata 5 field, manifest, idempotent + xoá chunk mồ côi) — 2026-07-09
- [x] Bước 3: `tests/test_kb_manifest.py` — 2026-07-09
- [x] Bước 4: Chạy `ingest_rag.py` lần 1 → verify `manifest.json` sinh ra đúng; chạy lần 2 → verify idempotent (số chunk không đổi) — 2026-07-09 (39 maintenance + 25 safety = 64 chunk, ổn định qua 2 lần chạy; `chromadb collection.count()` xác nhận không nhân đôi)
- [x] Bước 5: Retrieval smoke test thủ công (query mẫu cho từng action_code/warning code) → ghi kết quả — 2026-07-09

**Kết quả retrieval smoke test (baseline cho GH-24):**

| Query | Top-1 | Top-2 | Top-3 | Đánh giá |
|---|---|---|---|---|
| action_code REPLACE_IMMEDIATELY | bms_warning_codes.md (0.699) | action_code_sop.md (0.632) | action_code_sop.md (0.585) | ✅ đúng chủ đề |
| action_code SCHEDULE_REPLACEMENT | action_code_sop.md (0.656) | battery_maintenance_sop.md (0.632) | bms_warning_codes.md (0.602) | ✅ đúng chủ đề |
| action_code SCHEDULE_MAINTENANCE | bms_warning_codes.md (0.689) | action_code_sop.md (0.670) | action_code_sop.md (0.656) | ✅ đúng chủ đề |
| action_code MONITOR | action_code_sop.md (0.620) | anomaly_soc_soh.md (0.563) | action_code_sop.md (0.528) | ✅ đúng chủ đề |
| warning TEMP_CRITICAL | anomaly_thermal.md (0.569) | thermal_runaway_response.md (0.465) | anomaly_thermal.md (0.464) | ✅ đúng chủ đề |
| warning VOLTAGE_CRITICAL | electrical_safety_sop.md (0.461) | ppe_matrix.md (0.459) | ppe_matrix.md (0.435) | ✅ đúng chủ đề |
| warning OVERCURRENT_CRITICAL | ppe_matrix.md (0.438) | anomaly_thermal.md (0.437) | ppe_matrix.md (0.380) | ⚠️ lệch nhẹ — `anomaly_electrical.md` (chứa RapidDischarge/OVERCURRENT threshold) nằm ở collection `maintenance`, không được `retrieve_safety()` query tới — hạn chế kiến trúc 2-collection sẵn có, không phải bug ingest |
| warning BATTERY_EOL / SOH_LOW | anomaly_soc_soh.md (0.625) | battery_maintenance_sop.md (0.537) | action_code_sop.md (0.475) | ✅ đúng chủ đề |
| 12V LiFePO4 pack | battery_12v_lifepo4.md (0.633/0.583/0.495) — cả 3 | | | ✅ đúng chủ đề tuyệt đối |

8/9 query có top-3 đúng chủ đề. Điểm yếu duy nhất (OVERCURRENT_CRITICAL) là do ranh giới collection maintenance/safety, không phải lỗi chunking/ingest — đáng note cho GH-24.
- [x] Bước 6: `pytest tests/ -q --cov=src` — không regression, coverage giữ ≥85% — 2026-07-09 (347 test PASS, aggregate coverage 90%, `test_kb_manifest.py` 4/4 PASS, `ruff check` sạch)

## Câu hỏi đã giải đáp
1. **Ai viết nội dung 12 tài liệu KB mới?** — Claude tự draft, dựa trên citation đã có sẵn trong `ai-research-references.md` B2 §1 (không bịa threshold/standard mới), giữ format giống 4 doc hiện có. User sẽ tự review nội dung kỹ thuật trước khi nộp bảo vệ KLTN (Claude không có full-text các standard trả phí như IEC/NFPA nên không thể tự verify 100%).
