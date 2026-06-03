# Skill: /kltn-debug (AI)

## Kích hoạt
`/kltn-debug [issue-number]` — fix bug từ issue được tạo bởi log sheet.

---

## ACTION-FIRST RULE

**Đọc issue body thực sự TRƯỚC khi viết bất cứ điều gì.**

```bash
gh issue view $ISSUE_NUMBER --json number,title,body,labels
```

Tool calls trước, text output sau. Không đoán lỗi từ title.

---

## Phân tích lỗi AI

### 1. Đọc mô tả lỗi

Từ body issue, xác định:
- **Error type:** `FileNotFoundError`, `ValueError`, `AssertionError`, HTTP 422/500 từ FastAPI...
- **Script / endpoint** bị lỗi (`train.py`, `inference.py`, `/predict`, `/health`...)
- **Input** gây lỗi nếu có (shape, dtype, missing field)
- **Expected vs Actual output** (metric quá thấp, output sai kiểu...)

### 2. Trace nguyên nhân theo layer

```
FastAPI endpoint → inference pipeline → model → scaler → input data
                                                        ↑
                                         training pipeline (nếu lỗi liên quan model)
```

### 3. Common root causes AI

| Triệu chứng | Nguyên nhân thường gặp |
|------------|----------------------|
| `FileNotFoundError: scaler.pkl` | Chưa chạy training hoặc path sai — check `models/weights/` |
| `AssertionError: Scaler version mismatch` | Model và scaler version không khớp — retrain hoặc sync version |
| `ValueError: Input shape mismatch` | Window size hoặc số features không đúng 30×3 — check preprocessing |
| Inference latency > 100ms | Model load mỗi request thay vì 1 lần startup — check `lifespan` |
| HTTP 422 Unprocessable Entity | Pydantic schema không khớp với request body — check field name/type |
| Metric quá thấp (MAE > 2%) | Scaler fit trên toàn bộ data (data leakage) — chỉ fit trên train set |
| Kết quả không reproducible | Thiếu `random_seed = 42` hoặc thiếu `torch.manual_seed(42)` |
| `ModuleNotFoundError` khi import | Missing dependency trong `requirements.txt` |
| `NaN` loss khi train | Learning rate quá cao hoặc data có NaN — check input |

### 4. Verify trước khi fix

```bash
# Lint + format
ruff check [file-đã-sửa]
ruff format [file-đã-sửa]

# Chạy test liên quan
pytest tests/ -x -q -k "test_inference or test_preprocess"

# Nếu fix liên quan inference — benchmark latency
python -c "
import time, joblib, torch
# ... load model + scaler + chạy 10 lần đo avg latency
"
```

---

## Checklist fix

- [ ] Fix đúng hypothesis — không sửa code không liên quan
- [ ] `random_seed = 42` còn đủ ở đầu script
- [ ] Scaler chỉ `.fit()` trên train set — không fit lại trên production data
- [ ] Model load 1 lần trong `lifespan` — không load mỗi request
- [ ] `scaler.pkl` path đúng: `models/weights/scaler.pkl`
- [ ] Input shape đúng: `(batch, 30, 3)`
- [ ] `ruff check` — không lỗi sau khi fix
- [ ] `pytest tests/ -x -q` — không fail sau khi fix

---

## Commit message

```
fix(#$ISSUE_NUMBER): [mô tả ngắn — ví dụ: load scaler from pkl instead of refit on production]
```
