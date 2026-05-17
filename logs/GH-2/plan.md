# Plan — GH-2: Setup AI Module Base Project Structure

## Metadata
- **Status:** SHIPPED
- **Role:** AI
- **Ngày:** 2026-05-17
- **Issue:** #2 — https://github.com/GSU26SE55/ai-module/issues/2
- **Sprint:** Sprint 1 (due: 2026-05-30)

## Mục tiêu
Khởi tạo toàn bộ source code cho AI module: cấu trúc thư mục, FastAPI app skeleton, model architecture code (SOHPredictor + IsolationForest), dummy artifacts để app có thể boot, unit tests cơ bản, và research doc về hướng tiếp cận dự đoán SOH + anomaly detection.

**Không** chạy training thật trong Sprint 1 — dummy artifacts đủ để app chạy và endpoint trả đúng format. Training thật sẽ thực hiện ở Sprint 3–4 khi NASA dataset sẵn sàng.

## Scope
**Trong scope:**
- Scaffold toàn bộ cấu trúc thư mục `src/`, `scripts/`, `data/`, `models/`, `tests/`
- Implement `SOHPredictor` (CNN-LSTM) và `classify_anomaly` theo đúng spec CLAUDE.md
- FastAPI app: `main.py`, routers (`/predict`, `/health`), schemas, services, core (config + model_loader)
- Scripts: `preprocess.py` skeleton, `train.py` skeleton, `create_dummy_artifacts.py`
- Tạo dummy artifacts (scaler.pkl, soh_lstm_v1.0.pth, isolation_forest_v1.0.pkl) và commit
- Unit tests: model forward pass shape, inference format + latency benchmark, preprocess utils
- `.gitignore` cập nhật (data/raw, data/processed)
- Research doc: `docs/ai-prediction-research.md`

**Ngoài scope:**
- Download NASA dataset và chạy training thật (Sprint 3–4)
- Đạt target metrics MAE <2%, RMSE <3%, F1 >0.80 (Sprint 4)
- IoT data pipeline (Sprint 8)
- CALCE / MIT dataset (chỉ dùng nếu NASA không đủ)

## Files
| File | Action | Ghi chú |
|------|--------|---------|
| `main.py` | create | FastAPI app entry point, load models at startup |
| `src/__init__.py` | create | package init |
| `src/models/__init__.py` | create | |
| `src/models/soh_predictor.py` | create | class SOHPredictor (Conv1d→LSTM→FC) |
| `src/models/anomaly_detector.py` | create | classify_anomaly() helper |
| `src/schemas/__init__.py` | create | |
| `src/schemas/predict.py` | create | PredictRequest, PredictResponse (Pydantic) |
| `src/routers/__init__.py` | create | |
| `src/routers/predict.py` | create | POST /predict |
| `src/routers/health.py` | create | GET /health |
| `src/services/__init__.py` | create | |
| `src/services/inference.py` | create | inference logic tách khỏi router |
| `src/core/__init__.py` | create | |
| `src/core/config.py` | create | MODEL_VERSION, paths, SCALER_VERSION |
| `src/core/model_loader.py` | create | load 3 artifacts tại startup |
| `scripts/preprocess.py` | create | skeleton: load NASA .mat → windows (30, 3) |
| `scripts/train.py` | create | skeleton: train SOHPredictor + IsolationForest |
| `scripts/create_dummy_artifacts.py` | create | tạo dummy artifacts cho dev |
| `data/README.md` | create | ghi nguồn dataset + convention |
| `models/weights/scaler.pkl` | create | dummy — commit để app boot |
| `models/weights/soh_lstm_v1.0.pth` | create | dummy — commit để app boot |
| `models/weights/isolation_forest_v1.0.pkl` | create | dummy — commit để app boot |
| `tests/__init__.py` | create | |
| `tests/test_models.py` | create | forward pass shape test |
| `tests/test_inference.py` | create | inference format + latency benchmark (<100ms) |
| `tests/test_preprocess.py` | create | preprocessing utils unit test |
| `docs/ai-prediction-research.md` | create | research: SOH prediction + anomaly detection approach |
| `.gitignore` | modify | thêm data/raw/, data/processed/, *.mat |

## Approach

- **Model layer** (`src/models/`): chỉ định nghĩa architecture — không load weights ở đây. `SOHPredictor` implement đúng spec: `Conv1d(3→32, k=3) → MaxPool1d(2) → LSTM(32→64, 2 layers, dropout=0.2) → Linear(64→32) → Linear(32→1)`.
- **Core layer** (`src/core/`): `model_loader.py` load 3 artifacts 1 lần khi startup, assert version match. `config.py` giữ tất cả constants (path, version).
- **Service layer** (`src/services/inference.py`): nhận raw numpy array, scale → tensor → forward → classify. Tách khỏi router để unit test không cần boot FastAPI.
- **Router layer** (`src/routers/`): validate input shape (30, 3), gọi service, trả `PredictResponse` với `inference_ms`.
- **Dummy artifacts**: chạy `scripts/create_dummy_artifacts.py` một lần → sinh 3 files với random weights/data + đúng metadata version → commit. App boot thành công, endpoint trả response đúng format (predict sai nhưng không crash).
- **Research doc**: tổng hợp lý do chọn CNN-LSTM (local pattern + temporal dependency), IsolationForest (unsupervised, phù hợp khi label ít), train/val/test split theo battery ID (tránh data leakage).

## Edge Cases
- `readings` sai shape (không phải 30×3) → HTTP 422 với message rõ ràng
- Artifact file thiếu khi startup → assert với error message chỉ rõ file nào thiếu (không để traceback cryptic)
- Version mismatch giữa scaler và model → assert ngay khi load
- Latency benchmark với dummy model phải < 100ms (dummy model nhỏ nên dễ đạt)

## Success Criteria
| Tiêu chí | Cách verify |
|----------|------------|
| App boot thành công với dummy artifacts | `uvicorn main:app` không có exception |
| `POST /predict` trả đúng schema | `curl` với input (30,3) → response có `soh_percent`, `classification`, `confidence`, `inference_ms` |
| `GET /health` trả status ok | `curl /health` → `{"status": "ok", ...}` |
| Unit tests pass ≥ 85% coverage | `pytest tests/ -v --cov=src` |
| Latency benchmark < 100ms | `test_inference.py::test_latency` pass |
| Docs research có đủ 2 phần | SOH prediction approach + Anomaly detection approach |

## Steps
- [x] Bước 1 — Tạo cấu trúc thư mục + `__init__.py` cho toàn bộ packages — 2026-05-17
- [x] Bước 2 — Implement `src/core/config.py` (constants, paths, versions) — 2026-05-17
- [x] Bước 3 — Implement `src/models/soh_predictor.py` (SOHPredictor class) — 2026-05-17
- [x] Bước 4 — Implement `src/models/anomaly_detector.py` (classify_anomaly) — 2026-05-17
- [x] Bước 5 — Implement `src/schemas/predict.py` (PredictRequest, PredictResponse) — 2026-05-17
- [x] Bước 6 — Implement `src/core/model_loader.py` (load 3 artifacts at startup) — 2026-05-17
- [x] Bước 7 — Implement `src/services/inference.py` (inference pipeline) — 2026-05-17
- [x] Bước 8 — Implement `src/routers/health.py` và `src/routers/predict.py` — 2026-05-17
- [x] Bước 9 — Implement `main.py` (FastAPI app + include routers + lifespan startup) — 2026-05-17
- [x] Bước 10 — Viết `scripts/create_dummy_artifacts.py` + chạy → sinh 3 files — 2026-05-17
- [x] Bước 11 — Viết `scripts/preprocess.py` skeleton + `scripts/train.py` skeleton — 2026-05-17
- [x] Bước 12 — Cập nhật `.gitignore` — 2026-05-17
- [x] Bước 13 — Viết `tests/test_models.py`, `tests/test_inference.py`, `tests/test_preprocess.py` — 2026-05-17
- [x] Bước 14 — Chạy `pytest --cov=src` → đạt ≥ 85% (27/27 PASS, 90% coverage) — 2026-05-17
- [x] Bước 15 — Viết `docs/ai-prediction-research.md` — 2026-05-17
- [x] Bước 16 — Boot app, test endpoint thủ công — 2026-05-17

## Câu hỏi đã giải đáp
- **Model artifacts Sprint 1:** Dùng dummy artifacts (random weights) — app boot được, endpoint trả đúng format. Training thật → Sprint 3–4.
- **src/ layout:** Tách 5 layer: models / schemas / routers / services / core — service layer tách riêng để unit test không cần FastAPI.
- **Unit tests:** Include trong task này — viết cùng lúc với code, đạt ≥ 85% coverage trước khi ship.
