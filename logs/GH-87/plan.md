# Plan — GH-87: Chuẩn hóa PrescribeResponse — embed nested prediction/anomaly/risk

## Metadata
- **Status:** PLANNING | **Role:** AI | **Ngày:** 2026-07-05
- **Issue:** #87 — https://github.com/GSU26SE55/ai-module/issues/87
- **Phụ thuộc:** GH-86 (đã implement trên branch `feat/GH-86-uncertainty-health-stage` — GH-87 nên làm
  TRÊN branch đó hoặc sau khi GH-86 merge, vì PredictionInfo đã có 3 field GH-86)

## Mục tiêu

gRPC là cổng chính, flow chuẩn = BE gọi **Prescribe duy nhất** → PrescribeResponse là last output
nhưng hiện không mang uncertainty GH-86 (`health_stage`/`stage_probabilities`/`stage_confidence`/
`is_borderline`/`soh_confidence`). Embed 3 block nested tái dùng message/schema có sẵn, sửa doc sai
`confidence`, cập nhật doc tích hợp BE. Zero forward pass thêm — các block đã được `run_inference()`
tính sẵn trong `run_prescription`, chỉ chưa trả ra.

## Scope

**Trong scope:**
1. `src/services/prescription.py` — `run_prescription()` trả thêm 3 key nested:
   `"prediction": prediction_result["prediction"]`, `"anomaly": prediction_result["anomaly"]`,
   `"risk": prediction_result["risk"]` (dict có sẵn, không tính lại).
2. `src/schemas/prescribe.py` — `PrescribeResponse` thêm 3 field **optional** (backward compatible):
   `prediction: PredictionInfo | None = None`, `anomaly: AnomalyInfo | None = None`,
   `risk: RiskInfo | None = None` (import từ `src/schemas/predict.py` — tái dùng, không define mới).
   Comment đánh dấu 4 flat field cũ (`soh_percent`/`risk_level`/`priority`/`action_code`) là
   deprecated — sẽ xóa cùng đợt GH-61.
3. `protos/ai_service.proto` — `PrescribeResponse` **append** field 19–21 (không reuse số cũ):
   `PredictionInfo prediction = 19; AnomalyInfo anomaly = 20; RiskInfo risk = 21;`
   + sửa stale comment field 9 PredictResponse (`confidence`): "MC Dropout soh_confidence" thay
   "|IsolationForest score|". Regen stub `python scripts/gen_proto.py`.
4. `src/grpc_server.py` — extract helper `_to_prediction_info(dict)`, `_to_anomaly_info(dict)`,
   `_to_risk_info(dict)` từ `_to_predict_response` (tránh duplicate mapping), dùng cho cả
   `_to_predict_response` lẫn `_to_prescribe_response`.
5. `src/schemas/predict.py` — sửa comment sai của flat `confidence` (là soh_confidence MC Dropout).
6. `docs/grpc-integration-be.md` — thêm mục: flow chuẩn Prescribe-only (1 call = 1 lần inference,
   tránh gọi Predict+Prescribe song song trên cùng readings vì MC Dropout mỗi lần khác nhau);
   bảng field mới; ghi chú 4 flat field deprecated.
7. Tests:
   - `tests/test_prescription.py` — nested blocks có mặt + `prediction.is_borderline`/`stage_confidence`
     tồn tại + giá trị `risk` nested khớp flat (`risk_level`/`priority`/`action_code` cùng nguồn).
   - `tests/test_grpc_server.py` — `FIXED_PRESCRIBE_RESULT` thêm 3 block; parity REST/gRPC cho
     Prescribe mở rộng sang nested (giống pattern parity Predict).

**Ngoài scope (không tự ý làm):**
- Xóa 13 flat field PredictResponse / 4 flat field PrescribeResponse (GH-61 — PR phối hợp BE,
  proto `reserved`)
- Đổi semantics `classification` vs `health_stage`
- gRPC standard health protocol (`grpc.health.v1`)

## Files

| File | Action | Ghi chú |
|------|--------|---------|
| `src/services/prescription.py` | modify | +3 key nested trong return dict |
| `src/schemas/prescribe.py` | modify | +3 optional field, import từ predict schemas |
| `protos/ai_service.proto` | modify | append 19–21 + sửa comment field 9 |
| `src/grpc_gen/*` | regen | `python scripts/gen_proto.py` |
| `src/grpc_server.py` | modify | extract 3 helper, map nested cho Prescribe |
| `src/schemas/predict.py` | modify | sửa comment `confidence` |
| `docs/grpc-integration-be.md` | modify | flow Prescribe-only + field mới |
| `tests/test_prescription.py` | modify | nested blocks + consistency |
| `tests/test_grpc_server.py` | modify | FIXED_PRESCRIBE_RESULT + parity nested |

## Approach — data flow

```
run_prescription()
  └─ run_inference() ──► prediction_result (đã có prediction/anomaly/risk nested)
       │                                │
       │ (hiện tại: chỉ lấy 4 giá trị flat)
       ▼                                ▼
  return {                      GH-87: trả nguyên 3 block
    soh_percent, risk_level,    "prediction": {...GH-86 fields...},
    priority, action_code,      "anomaly": {...},
    (deprecated)                "risk": {...},
    prescription, ...           ...
  }
```

REST: FastAPI serialize dict → PrescribeResponse (3 field optional).
gRPC: `_to_prescribe_response` map qua 3 helper dùng chung với Predict → parity tự nhiên.

## Steps
- [ ] Bước 1: `run_prescription` trả 3 block + `PrescribeResponse` schema → `pytest tests/test_prescription.py tests/test_routers.py`
- [ ] Bước 2: proto append 19–21 + sửa comment + regen → helpers trong grpc_server → `pytest tests/test_grpc_server.py tests/test_grpc_contract.py`
- [ ] Bước 3: sửa comment `confidence` (predict.py + proto đã gộp bước 2)
- [ ] Bước 4: cập nhật `docs/grpc-integration-be.md`
- [ ] Bước 5: full `pytest tests/ --cov=src` ≥85% + `python scripts/benchmark_grpc.py --real-weights` (Prescribe <100ms không đổi)
- [ ] Bước 6: `/kltn-reviewcode` → `/kltn-test 87`
