---
name: scaffold-unit-tests
description: Scaffold pytest test files cho AI module — preprocess, model forward/save-load, inference reproducibility, latency benchmark (<100ms), FastAPI endpoint validation
argument-hint: [module: preprocess|model|inference|api|all]
allowed-tools: Write, Read, Bash
---

# Scaffold Unit Tests `$ARGUMENTS`

Usage: `/scaffold-unit-tests [module]`
Modules: `preprocess` | `model` | `inference` | `api` | `all` (default khi không có argument)

---

## Bước 0 — Xác định scope

Từ `$ARGUMENTS`:
- `preprocess` → chỉ tạo `tests/test_preprocess.py`
- `model`       → chỉ tạo `tests/test_model.py`
- `inference`   → chỉ tạo `tests/test_inference.py`
- `api`         → chỉ tạo `tests/test_api.py`
- `all` / không có argument → tạo tất cả 4 file + `tests/conftest.py`

---

## Bước 1 — Tạo thư mục + cấu hình pytest

```bash
mkdir -p tests
touch tests/__init__.py
```

Tạo `pytest.ini` (nếu chưa có):
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

---

## Bước 2 — `tests/conftest.py` (chỉ khi scope = `all`)

```python
"""Shared pytest fixtures cho AI module."""
import random
import numpy as np
import torch
import pytest

SEED        = 42
WINDOW_SIZE = 30
BATCH_SIZE  = 4


@pytest.fixture(autouse=True)
def set_seed():
    """Set seed trước mỗi test — đảm bảo reproducibility."""
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)


@pytest.fixture
def sample_window() -> np.ndarray:
    """1 window: shape (30, 3) — voltage, current, temperature."""
    return np.random.rand(WINDOW_SIZE, 3).astype(np.float32)


@pytest.fixture
def sample_batch() -> np.ndarray:
    """Batch windows: shape (4, 30, 3)."""
    return np.random.rand(BATCH_SIZE, WINDOW_SIZE, 3).astype(np.float32)


@pytest.fixture
def sample_tensor(sample_batch: np.ndarray) -> torch.Tensor:
    return torch.tensor(sample_batch, dtype=torch.float32)
```

---

## Bước 3 — `tests/test_preprocess.py`

```python
"""Tests cho data/preprocess.py."""
import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import MinMaxScaler

from data.preprocess import build_windows, _apply_scaler


def _make_df(n: int = 50) -> pd.DataFrame:
    return pd.DataFrame({
        "voltage":     np.linspace(3.5, 4.2, n),
        "current":     np.linspace(0.5, 2.0, n),
        "temperature": np.linspace(20,  35,  n),
        "capacity":    np.linspace(1.8, 2.0, n),
        "soh":         np.linspace(90,  100, n),
    })


class TestBuildWindows:
    def test_output_shape(self):
        X, y = build_windows(_make_df(50), window_size=30)
        assert X.shape == (20, 30, 3)   # 50 - 30 = 20 windows
        assert y.shape == (20,)

    def test_soh_in_range(self):
        _, y = build_windows(_make_df())
        assert (y >= 0).all() and (y <= 100).all()

    def test_no_data_leakage(self):
        """Window đầu tiên phải là timestep 0–29, không lấy từ vị trí sau."""
        n  = 40
        df = pd.DataFrame({
            "voltage":     np.arange(n, dtype=float),
            "current":     np.zeros(n),
            "temperature": np.zeros(n),
            "capacity":    np.ones(n) * 2.0,
            "soh":         np.ones(n) * 100.0,
        })
        X, _ = build_windows(df, window_size=30)
        np.testing.assert_array_equal(X[0, :, 0], np.arange(30, dtype=float))

    def test_minimum_data_required(self):
        """DataFrame ngắn hơn window_size không tạo được window nào."""
        X, y = build_windows(_make_df(10), window_size=30)
        assert len(X) == 0 and len(y) == 0


class TestApplyScaler:
    def test_output_range(self):
        X      = np.random.rand(10, 30, 3).astype(np.float32)
        scaler = MinMaxScaler().fit(X.reshape(-1, 3))
        X_s    = _apply_scaler(X, scaler)
        assert X_s.min() >= -1e-6
        assert X_s.max() <= 1.0 + 1e-6

    def test_shape_preserved(self):
        X      = np.random.rand(5, 30, 3).astype(np.float32)
        scaler = MinMaxScaler().fit(X.reshape(-1, 3))
        assert _apply_scaler(X, scaler).shape == X.shape

    def test_dtype_float32(self):
        X      = np.random.rand(3, 30, 3).astype(np.float32)
        scaler = MinMaxScaler().fit(X.reshape(-1, 3))
        assert _apply_scaler(X, scaler).dtype == np.float32
```

---

## Bước 4 — `tests/test_model.py`

```python
"""Tests cho models/soh_predictor.py và models/anomaly_detector.py."""
import numpy as np
import torch
import pytest

from models.soh_predictor  import SOHPredictor
from models.anomaly_detector import AnomalyDetector


class TestSOHPredictor:
    def test_forward_output_shape(self, sample_tensor: torch.Tensor):
        model = SOHPredictor()
        model.eval()
        with torch.no_grad():
            out = model(sample_tensor)
        assert out.shape == (sample_tensor.shape[0],)

    def test_forward_single_window(self, sample_window: np.ndarray):
        model = SOHPredictor()
        model.eval()
        x = torch.tensor(sample_window).unsqueeze(0)   # (1, 30, 3)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1,)

    def test_save_load_roundtrip(self, tmp_path: pytest.TempdirFactory, sample_tensor: torch.Tensor):
        model = SOHPredictor()
        model.eval()
        path  = str(tmp_path / "soh_lstm_v1.0.pth")
        model.save(path, version="1.0")

        loaded = SOHPredictor.load(path, expected_version="1.0")
        with torch.no_grad():
            orig   = model(sample_tensor)
            loaded_out = loaded(sample_tensor)
        torch.testing.assert_close(orig, loaded_out)

    def test_load_version_mismatch_raises(self, tmp_path: pytest.TempdirFactory):
        model = SOHPredictor()
        path  = str(tmp_path / "model.pth")
        model.save(path, version="1.0")
        with pytest.raises(AssertionError, match="version mismatch"):
            SOHPredictor.load(path, expected_version="2.0")


class TestAnomalyDetector:
    def _fitted_model(self, sample_batch: np.ndarray) -> AnomalyDetector:
        model  = AnomalyDetector()
        n, w, f = sample_batch.shape
        model.fit(sample_batch.reshape(n, w * f))
        return model

    def test_score_shape(self, sample_batch: np.ndarray):
        model  = self._fitted_model(sample_batch)
        n, w, f = sample_batch.shape
        scores = model.score(sample_batch.reshape(n, w * f))
        assert scores.shape == (n,)

    def test_classify_returns_valid_label(self, sample_batch: np.ndarray):
        model  = self._fitted_model(sample_batch)
        n, w, f = sample_batch.shape
        score  = float(model.score(sample_batch.reshape(n, w * f))[0])
        label  = model.classify(score, soh=85.0)
        assert label in ("Normal", "Degrading", "Failed")

    def test_score_without_fit_raises(self):
        model = AnomalyDetector()
        with pytest.raises(AssertionError):
            model.score(np.zeros((1, 90)))

    def test_save_load_roundtrip(self, tmp_path: pytest.TempdirFactory, sample_batch: np.ndarray):
        model  = self._fitted_model(sample_batch)
        path   = str(tmp_path / "iso_v1.0.pkl")
        model.save(path, version="1.0")

        loaded = AnomalyDetector.load(path, expected_version="1.0")
        n, w, f = sample_batch.shape
        X_flat = sample_batch.reshape(n, w * f)
        np.testing.assert_array_equal(model.score(X_flat), loaded.score(X_flat))
```

---

## Bước 5 — `tests/test_inference.py`

```python
"""Tests reproducibility và latency benchmark cho inference pipeline."""
import time
import numpy as np
import torch
import pytest

from models.soh_predictor  import SOHPredictor
from models.anomaly_detector import AnomalyDetector

LATENCY_THRESHOLD_MS = 100
WARMUP_RUNS          = 5
BENCHMARK_RUNS       = 50


class TestReproducibility:
    def test_soh_deterministic(self, sample_window: np.ndarray):
        """Cùng input, chạy inference 2 lần → cùng kết quả."""
        model = SOHPredictor()
        model.eval()
        x = torch.tensor(sample_window).unsqueeze(0)
        with torch.no_grad():
            r1 = model(x).item()
            r2 = model(x).item()
        assert r1 == r2, f"SOH không reproducible: {r1} ≠ {r2}"

    def test_anomaly_deterministic(self, sample_batch: np.ndarray):
        """Isolation Forest cho cùng score với cùng input."""
        model  = AnomalyDetector()
        n, w, f = sample_batch.shape
        X_flat = sample_batch.reshape(n, w * f)
        model.fit(X_flat)
        np.testing.assert_array_equal(model.score(X_flat), model.score(X_flat))


class TestLatency:
    def test_soh_inference_under_100ms(self, sample_window: np.ndarray):
        """Inference trung bình phải < 100ms — P1 SLA yêu cầu real-time alert."""
        model = SOHPredictor()
        model.eval()
        x = torch.tensor(sample_window).unsqueeze(0)

        for _ in range(WARMUP_RUNS):
            with torch.no_grad():
                model(x)

        latencies = []
        for _ in range(BENCHMARK_RUNS):
            t0 = time.perf_counter()
            with torch.no_grad():
                model(x)
            latencies.append((time.perf_counter() - t0) * 1000)

        avg_ms = sum(latencies) / len(latencies)
        print(f"\n  Avg inference: {avg_ms:.1f}ms  (threshold={LATENCY_THRESHOLD_MS}ms)")
        assert avg_ms < LATENCY_THRESHOLD_MS, (
            f"Inference quá chậm: {avg_ms:.1f}ms > {LATENCY_THRESHOLD_MS}ms"
        )
```

---

## Bước 6 — `tests/test_api.py`

```python
"""Tests cho FastAPI endpoint — health check, predict schema, error handling."""
import numpy as np
import pytest

try:
    from fastapi.testclient import TestClient
    from api.main import app
    client        = TestClient(app)
    APP_AVAILABLE = True
except Exception as _e:
    APP_AVAILABLE = False
    _SKIP_REASON  = f"API không load được (artifacts chưa có?): {_e}"


def _skip_if_no_app():
    return pytest.mark.skipif(
        not APP_AVAILABLE,
        reason=_SKIP_REASON if not APP_AVAILABLE else "",
    )


def _payload(n: int = 30) -> dict:
    return {
        "voltage":     list(np.random.uniform(3.5, 4.2, n).round(3)),
        "current":     list(np.random.uniform(0.5, 2.0, n).round(3)),
        "temperature": list(np.random.uniform(20,  35,  n).round(3)),
    }


@_skip_if_no_app()
class TestHealth:
    def test_status_ok(self):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_all_artifacts_loaded(self):
        body = client.get("/health").json()
        assert body.get("scaler_loaded") is True
        assert body.get("lstm_loaded")   is True
        assert body.get("isolation_forest_loaded") is True


@_skip_if_no_app()
class TestPredict:
    def test_valid_request_200(self):
        assert client.post("/predict", json=_payload()).status_code == 200

    def test_response_schema(self):
        body = client.post("/predict", json=_payload()).json()
        assert body["status"] in ("Normal", "Degrading", "Failed")
        assert 0.0 <= body["soh_percent"] <= 100.0
        assert 0.0 <= body["confidence"]  <= 1.0

    def test_missing_field_422(self):
        p = _payload()
        del p["voltage"]
        assert client.post("/predict", json=p).status_code == 422

    def test_empty_list_422(self):
        p = _payload()
        p["voltage"] = []
        assert client.post("/predict", json=p).status_code == 422

    def test_insufficient_timesteps_422(self):
        """Gửi < 30 timestep phải trả về 422."""
        assert client.post("/predict", json=_payload(n=10)).status_code == 422

    def test_soh_boundary_not_crash(self):
        """Endpoint không crash với input edge case."""
        p = _payload()
        p["voltage"]     = [4.2] * 30
        p["current"]     = [0.01] * 30
        p["temperature"] = [20.0] * 30
        res = client.post("/predict", json=p)
        assert res.status_code == 200
```

---

## Bước 7 — Chạy tests

```bash
pytest tests/ -v \
  --cov=api --cov=data --cov=models --cov=train \
  --cov-report=term-missing
# Target: ≥ 85% line coverage
```

---

## Checklist sau scaffold

- [ ] `conftest.py` có `autouse=True` seed fixture?
- [ ] `test_preprocess.py` test shape, range, no-leakage, short-df edge case?
- [ ] `test_model.py` test forward shape, save/load roundtrip, version mismatch?
- [ ] `test_inference.py` test reproducibility + latency < 100ms?
- [ ] `test_api.py` test 200 valid, schema, 422 missing/empty/short-input?
- [ ] pytest.ini đã tồn tại?

---

## Không được
- Dùng production model weights trong tests — dùng random-initialized model
- Hardcode input data thay vì fixtures
- Đặt latency threshold > 100ms
- Skip `test_api.py` khi artifacts chưa có — dùng `skipif` để báo rõ lý do
