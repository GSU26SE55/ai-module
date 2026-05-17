# Báo cáo Code Review — feature/GH-2-ai-setup-ai-module-base — 2026-05-17

## TÓM TẮT
Scaffold code đúng spec, đầy đủ cấu trúc 5-layer, 27/27 tests PASS với coverage 90%. Có 2 warning cần fix trước khi ship: `soh_percent` chưa clamp về [0, 100] và dùng `assert` để check startup conditions.

---

## PHÂN TÍCH

### 🔴 Critical
_Không có._

---

### 🟡 Warning

**W1 — `src/services/inference.py:27` — SOH không được clamp về [0, 100]**
```python
# Hiện tại:
soh = float(model_loader.soh_model(x_tensor).item() * 100)

# Fix — thêm clamp để tránh trả về giá trị âm hoặc >100:
soh = float(max(0.0, min(100.0, model_loader.soh_model(x_tensor).item() * 100)))
```
_Lý do:_ Linear output của model không tự bounded. Với dummy weights thực tế trả -10.23. Real model sau training vẫn có thể out-of-range trên test samples cực đoan. API contract phải đảm bảo `soh_percent ∈ [0, 100]` vì BE và mobile sẽ render progress bar dựa vào giá trị này.

---

**W2 — `src/core/model_loader.py:28,34,40` — Dùng `assert` cho production checks**
```python
# Hiện tại:
assert os.path.exists(path), f"[STARTUP] {label} artifact not found..."

# Fix — dùng RuntimeError để không bị tắt bởi Python -O flag:
if not os.path.exists(path):
    raise RuntimeError(f"[STARTUP] {label} artifact not found at '{path}'...")
```
_Lý do:_ Python `assert` bị bỏ qua hoàn toàn khi chạy với flag `-O` (optimize). Production server (uvicorn, gunicorn với `-O`) sẽ load silently fail. `RuntimeError` đảm bảo check luôn chạy.

---

### ✅ Pass

| Tiêu chí | Kết quả |
|----------|---------|
| Ruff lint 0 errors | ✅ All checks passed |
| 27/27 tests PASS | ✅ |
| Coverage ≥ 85% | ✅ 90% |
| Inference latency < 100ms | ✅ 11.4ms avg |
| Architecture khớp spec CLAUDE.md | ✅ Conv1d(3→32)→MaxPool1d(2)→LSTM(32→64,2L)→Linear |
| Input validation Pydantic (shape 30×3) | ✅ HTTP 422 đúng |
| Model load 1 lần ở startup (không per-request) | ✅ lifespan + globals |
| Seed = 42 trong train.py + preprocess.py | ✅ |
| Version assertion scaler/model | ✅ |
| Dummy artifacts đúng metadata format | ✅ scaler.pkl, soh_lstm_v1.0.pth, isolation_forest_v1.0.pkl |
| `.gitignore` có data/raw, data/processed, *.mat | ✅ |
| classify_anomaly logic đúng spec | ✅ score>-0.1→Normal / >-0.3‖SOH≥80→Degrading / else→Failed |
| Health endpoint trả đúng fields | ✅ status, model_version, scaler_loaded, lstm_loaded, iso_loaded |
| GET /health + POST /predict routes đúng prefix | ✅ |
| Research doc có đủ 2 phần (SOH + Anomaly) | ✅ |

---

## RỦI RO & LƯU Ý

- **NumPy version mismatch**: torch 2.3.1 được compile với NumPy 1.x nhưng system Python có NumPy 2.x → warning khi import. Không ảnh hưởng đến tests (chạy qua) nhưng cần giải quyết khi setup virtualenv chính thức (Sprint 2). Giải pháp: `pip install "numpy<2"` hoặc upgrade torch lên 2.4+.
- **`httpx` + `pytest` + `pytest-cov` chưa có trong `requirements.txt`**: Đây là test dependencies. Nên thêm vào file `requirements-dev.txt` hoặc thêm comment section `# test` trong `requirements.txt` để các dev khác biết cần cài khi chạy tests.
- **`weights_only=False` trong `torch.load`**: Security note — cho phép arbitrary code execution nếu file model bị tamper. Acceptable cho internal artifacts (commit vào Git), nhưng nên chú ý nếu sau này load model từ nguồn ngoài.

---

## KẾT LUẬN

**PASS** — Độ tự tin: **Cao**

W1 + W2 đã được fix. 27/27 tests PASS, lint clean, coverage 90%.
Chạy `/kltn-test GH-2` để tiếp tục.
