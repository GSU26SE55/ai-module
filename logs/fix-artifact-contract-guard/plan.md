# Plan — fix/artifact-contract-guard

## Metadata

- **Status:** DONE (B1-B7) · **Role:** AI · **Ngày:** 2026-08-07
- **Nhánh:** `fix/artifact-contract-guard` (tách từ `dev` sau khi merge `feat/connect-be`)
- **Issue:** không có — user yêu cầu làm thẳng, không lên issue

## Mục tiêu

Bịt **lớp lỗi "thứ dùng chung bị đổi mà không ai biết"**. Lớp này đã cắn 6 lần:

| Lần | Thứ bị đổi | Hậu quả |
|---|---|---|
| 1–5 | Hằng số hiệu chỉnh theo NASA (`TEMPERATURE_TRAIN_CLUSTERS`, `CYCLE_COUNT_NORM`, `DEGRADATION_RATE`, `VOLTAGE_CELL_RANGE`, `NOMINAL_CAPACITY_AH`) | Trả số sai âm thầm trên đường LFP |
| 6 | `extract_window_features()` thêm Gini (`e3f93da`, 2026-06-27) | Checkpoint RUL lưu 2026-06-17 với `feat_dim=54` chết hẳn |

Đặc điểm chung: **không làm sập gì cả lúc thay đổi**, chỉ lộ ra rất lâu sau, khi chạy dữ liệu thật.

Kèm 2 việc dọn cùng gốc: test đỏ giả trên Windows, và churn nhị phân của vector store.

## Scope

**Trong scope:**
1. Guard `feat_dim` — chặn artifact lệch hợp đồng đặc trưng
2. Băm manifest chuẩn hoá LF ở **cả** script ingest lẫn test
3. Quyết định hướng xử churn `models/embeddings/` (mục "Cần quyết" bên dưới)

**Ngoài scope:** train lại RUL/Forecast · sklearn 1.5.0→1.6.1 · đặc trưng IC cho LFP · 8 lỗi ruff có sẵn.

---

## Số liệu đã đo (cơ sở của plan)

```
SPECTRAL_FEAT_DIM = 57                         (src/core/config.py:87)
extract_window_features(3 kênh) -> 57          khớp
inference.py:349  extract_window_features(x_scaled[:, :3])   -> 3 kênh

feat_dim trong từng checkpoint:
  soh_mamba_v1.6.pth       57  ✅ (production NASA)
  soh_mamba_v2.0-lfp.pth   57  ✅ (production LFP)
  soh_mamba_long_v2.2.pth  57  ✅
  soh_mamba_rul_v1.0.pth   54  ❌ chết
  soh_mamba_v1.1/v1.2.pth  54  ❌ (không dùng production)
  soh_mamba_v1.0.pth       KHÔNG CÓ KHOÁ feat_dim

Băm knowledge/: 6/6 file khớp manifest bằng LF · 0/6 khớp bằng CRLF
```

Ba loader hiện dùng `checkpoint.get("feat_dim", SPECTRAL_FEAT_DIM)` — **âm thầm rơi về mặc định**
khi thiếu khoá (`model_loader.py:109, 243, 296`). Không có loader RUL nào trong `src/`.

---

## Files

| File | Action | Ghi chú |
|---|---|---|
| `src/core/model_loader.py` | modify | Thêm `_assert_feat_dim()`, gọi ở 3 loader |
| `scripts/ingest_rag.py` | modify | `sha256_file()` chuẩn hoá CRLF→LF |
| `tests/test_kb_manifest.py` | modify | `_sha256_file()` chuẩn hoá giống hệt |
| `tests/test_model_loader.py` | modify | Test cho guard |
| `tests/test_extractor.py` | modify | Test chốt `SPECTRAL_FEAT_DIM` == chiều thật của extractor |

Không đụng `models/weights/` — không train lại gì.

---

## Approach

### 1. Guard `feat_dim` — hai lớp

**Lớp A — test tĩnh (giá trị cao nhất, 1 dòng assert).**

```python
assert SPECTRAL_FEAT_DIM == extract_window_features(np.zeros((30, 3), np.float32)).shape[0]
```

Đỏ **ngay khoảnh khắc** ai đó sửa `extract_window_features()`, trước khi kịp lưu checkpoint nào.
Chính đây là thứ đáng ra phải chặn commit Gini từ 2026-06-27.

**Lớp B — guard lúc load.** So `checkpoint["feat_dim"]` với `SPECTRAL_FEAT_DIM`.

Xử lý khác nhau theo từng bộ, có chủ ý:

| Loader | Lệch thì làm gì | Vì sao |
|---|---|---|
| `load_models()` (NASA mặc định) | **raise** — service không boot | Thiếu bộ này thì service vô dụng; hỏng sớm rõ ràng hơn là chấm sai |
| `load_lfp_models()` | log **error** + không set artifact | Khớp hành vi sẵn có khi thiếu file LFP. `_resolve_artifacts("LFP")` vốn đã từ chối rơi về NASA, nên request LFP sẽ nhận `RuntimeError` rõ ràng |
| `load_long_model()` | **raise** | Lazy-load, chỉ ảnh hưởng `PredictLong` |

Thiếu hẳn khoá `feat_dim` (như `v1.0`): **warning**, không raise — artifact cũ trước khi có khoá này,
và không nằm trên đường production.

Thông báo lỗi phải nói **làm gì tiếp**, không chỉ nói sai:

```
soh_mamba_v1.6.pth lưu với feat_dim=54 nhưng extract_window_features() hiện sinh 57
đặc trưng (SPECTRAL_FEAT_DIM). Checkpoint được lưu TRƯỚC một thay đổi của extractor
(vd commit e3f93da thêm Gini). Train lại artifact, hoặc checkout đúng commit extractor
tương ứng — KHÔNG sửa SPECTRAL_FEAT_DIM cho khớp, làm thế là chấm bằng đặc trưng sai.
```

Dòng cuối quan trọng: cách "sửa" sai lầm tự nhiên nhất là hạ `SPECTRAL_FEAT_DIM` xuống 54.

### 2. Băm manifest theo LF

```python
def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
```

Phải sửa **cả hai** chỗ cùng lúc — sửa một chỗ thì hai bên vẫn lệch, chỉ đổi bên nào đỏ.

**Không cần chạy lại `ingest_rag.py`**: manifest hiện tại sinh trong container (LF), và đã đo 6/6 file
khớp bằng LF. Sau khi chuẩn hoá, máy Windows băm ra đúng con số đó.

---

## Steps

- [x] B1. Test tĩnh `SPECTRAL_FEAT_DIM` == chiều thật của extractor (`tests/test_extractor.py`)
- [x] B2. `_assert_feat_dim()` trong `model_loader.py` + gọi ở 3 loader
- [x] B3. Test guard: khớp thì qua · lệch thì raise · thiếu khoá thì chỉ warning
- [x] B4. Chuẩn hoá LF ở `ingest_rag.py` **và** `tests/test_kb_manifest.py`
- [x] B5. Chạy `pytest` — kỳ vọng `test_kb_manifest` chuyển từ đỏ sang xanh, không phát sinh lỗi mới
- [x] B6. Chạy `ruff` — không được thêm lỗi mới (baseline 8: 5 E402 + 2 E702 + 1 F401 code sinh)
- [x] B7. Chạy `scripts/e2e_full_test.py` — service vẫn boot và chấm đúng với artifact hiện tại

**Tiêu chí PASS:** `pytest` 635 passed 0 failed · ruff không lỗi mới · e2e TẤT CẢ PASS.

---

## ⚠️ Cần quyết trước khi làm — churn `models/embeddings/`

Đã truy nguyên: **không phải do re-ingest.** `ingest_rag.py` chỉ chạy tay, không ai gọi lúc khởi động.
Churn đến từ chính **ChromaDB ghi vào store mỗi khi mở** (`length.bin`, `chroma.sqlite3` 1.40→1.85 MB).
Vừa xảy ra ngay trong merge này: 2 file `.bin` bị ghi lại **sau khi** đã staged.

Nên không "sửa" được bằng cách thêm điều kiện skip. Hai hướng thật:

| | Cách làm | Được | Mất |
|---|---|---|---|
| **A** | Bỏ commit store, chỉ commit `knowledge/` + `manifest.json`; build store lúc build image (`RUN python scripts/ingest_rag.py`) | Hết churn hẳn. Store thành **artifact dẫn xuất**, đúng bản chất | Build image cần mạng để tải `all-MiniLM-L6-v2`. Phải sửa `.dockerignore` (đang ghi rõ **KHÔNG** được ignore `models/embeddings/`) |
| **B** | Chuyển store ra thư mục ngoài repo, mount thành docker volume như `ai-prescription-history` | Hết churn, không đụng build | Thêm một bước chuẩn bị lúc deploy; máy mới phải ingest một lần |

Nghiêng về **A** — nó biến store thành thứ sinh ra được từ `knowledge/`, thay vì một khối nhị phân
1.85 MB phải giữ đồng bộ bằng tay. Nhưng nó đụng Dockerfile và cách deploy nên **cần bạn chốt**.

Nếu chưa muốn quyết: làm B1–B7 trước, để churn lại xử riêng. Hai việc kia độc lập hoàn toàn.


---

## Kết quả (2026-08-07)

```
pytest : 640 passed, 0 failed      (trước: 634 passed + 1 failed)
ruff   : 35 — đúng baseline, các file đã sửa đều "All checks passed"
e2e    : TẤT CẢ PASS
```

`test_kb_manifest` chuyển từ **đỏ sang xanh** mà không phải chạy lại `ingest_rag.py` —
đúng như dự đoán, vì manifest vốn băm theo LF.

### Khác plan một điểm: bỏ cờ `strict`

Plan định cho `_resolve_feat_dim()` một cờ `strict` để LFP degrade còn NASA thì raise.
Khi implement mới thấy **cờ đó không làm gì cả**: `load_lfp_models()` vốn đã nằm trong
`try/except Exception` sẵn (`model_loader.py:201`), nên raise ở đó tự động degrade rồi.

Bỏ cờ đi — hàm luôn `raise RuntimeError`, **call site quyết định hậu quả**:

| Loader | Bọc try? | Lệch feat_dim thì |
|---|---|---|
| `load_models()` | không | service không boot |
| `load_lfp_models()` | có (sẵn) | log warning, artifact = None, request LFP nhận lỗi rõ ràng |
| `load_long_model()` | không | chỉ `PredictLong` hỏng |

Có test khoá điều này (`test_lfp_mismatch_degrades_instead_of_killing_the_service`) —
nó soi source `load_models()` để chắc `load_lfp_models()` còn nằm trong `try`. Ai gỡ
`try` đi thì test đỏ.

### Ghi chú kỹ thuật khi sửa B4

Chuỗi escape `
` bị nuốt qua nhiều tầng (heredoc → Python → `re.sub` diễn giải escape
trong chuỗi thay thế). Phải dùng **lambda** làm replacement (chặn `re` diễn giải) **và**
dựng dấu backslash gián tiếp bằng `chr(92)`. Ghi lại để lần sau sửa code có escape thì
biết đường.

## Còn lại

- Churn `models/embeddings/` — **chưa làm**, chờ chốt hướng A hay B (xem mục "Cần quyết")
- Train lại RUL + Forecast · sklearn 1.5.0→1.6.1 · đặc trưng IC cho LFP — đợt sau
