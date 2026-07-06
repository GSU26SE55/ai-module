"""
GH-40 — gRPC server unary tests: servicer behavior, REST parity,
error codes, and latency. Uses the dummy-loader pattern from
test_routers.py; the parity tests patch run_inference/run_prescription
with a fixed dict (MC Dropout makes two real calls non-deterministic).
"""

import time
from concurrent import futures
from unittest.mock import patch

import grpc
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.core import model_loader
from src.core.config import BASE_FEATURES, INPUT_FEATURES, MODEL_VERSION, WINDOW_SIZE
from src.grpc_gen import ai_service_pb2 as pb
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc
from src.grpc_server import AiServiceServicer
from tests.test_routers import make_dummy_loader

BASE_N = len(
    BASE_FEATURES
)  # GH-54: API payload width (4) — model input is INPUT_FEATURES (6)

# GH-66: values must be physically realistic — the range guard rejects the old
# rand()∈[0,1) rows (voltage 0.37V < 2.0V floor). Deterministic (seed 42).
_rng = np.random.RandomState(42)
VALID_READINGS = [
    pb.Reading(
        values=[
            3.5 + 0.6 * _rng.rand(),  # voltage [3.5, 4.1] V — under the 4.15V warning line
            -2.0 + 4.0 * _rng.rand(),  # current [-2, 2] A
            20.0 + 10.0 * _rng.rand(),  # temperature [20, 30] °C
            float(i * 10),  # time (s, cumulative)
        ]
    )
    for i in range(WINDOW_SIZE)
]

# GH-56 — 6-col payload: BE sends cycle_count (constant, raw index) + soc_percent
# (raw 0-100, varies per timestep) as columns 5-6 instead of AI deriving them.
_rng6 = np.random.RandomState(42)
VALID_READINGS_6COL = [
    pb.Reading(
        values=[
            3.5 + 0.6 * _rng6.rand(),
            -2.0 + 4.0 * _rng6.rand(),
            20.0 + 10.0 * _rng6.rand(),
            float(i * 10),
            42.0,
            100.0 - i,
        ]
    )
    for i in range(WINDOW_SIZE)
]

# GH-77 — named-field equivalents of VALID_READINGS / VALID_READINGS_6COL,
# built from the exact same values so array vs object-format parity tests
# compare identical numbers.
VALID_READING_FIELDS = [
    pb.ReadingFields(
        voltage=r.values[0],
        current=r.values[1],
        temperature=r.values[2],
        time=r.values[3],
    )
    for r in VALID_READINGS
]
VALID_READING_FIELDS_6COL = [
    pb.ReadingFields(
        voltage=r.values[0],
        current=r.values[1],
        temperature=r.values[2],
        time=r.values[3],
        cycle_count=r.values[4],
        soc_percent=r.values[5],
    )
    for r in VALID_READINGS_6COL
]

FIXED_PREDICT_RESULT = {
    "prediction": {
        "soh_percent": 87.5,
        "soh_confidence": 0.92,
        "soh_std": 1.3,
        "rul_cycles_estimate": 120,
        "degradation_rate_per_cycle": 0.15,
        "soh_trend": "stable",
        "cycles_to_maintenance": 17,
        "soh_trajectory": [87.5, 87.35, 87.2, 87.05, 86.9],
        "health_stage": "mid-life",
        # GH-86: MC-distribution staging
        "stage_probabilities": {
            "End Of Life": 0.0,
            "Maintenance Required": 0.1,
            "Degrading": 0.9,
            "Healthy": 0.0,
        },
        "stage_confidence": 0.9,
        "is_borderline": False,
    },
    "anomaly": {
        "anomaly_score": -0.05,
        "anomaly_status": "Normal",
        "anomaly_confidence": 0.05,
    },
    "risk": {
        "risk_level": "Low",
        "priority": "P3",
        "action_code": "MONITOR",
        "reasons": ["SOH healthy"],
    },
    "evidence": {
        "warnings": [{"code": "SOH_LOW", "severity": "warning", "message": "watch"}],
        "feature_summary": {"voltage": {"mean": 3.7, "min": 3.2, "max": 4.2}},
    },
    "metadata": {
        "model_version": "1.0",
        "window_size": WINDOW_SIZE,
        "input_features": INPUT_FEATURES,
        "inference_ms": 12.3,
        "n_series": 1,  # GH-65
        "temperature_domain_distance": 1.0,  # GH-91
        "is_temperature_ood": False,  # GH-91
    },
    "soh_percent": 87.5,
    "classification": "Normal",
    "confidence": 0.92,
    "inference_ms": 12.3,
    "rul_cycles_estimate": 120,
    "degradation_rate_per_cycle": 0.15,
    "soh_trend": "stable",
    "cycles_to_maintenance": 17,
    "soh_trajectory": [87.5, 87.35, 87.2, 87.05, 86.9],
    "anomaly_score": -0.05,
    "recommended_action": "MONITOR",
    "warnings": [{"code": "SOH_LOW", "severity": "warning", "message": "watch"}],
    "feature_summary": {"voltage": {"mean": 3.7, "min": 3.2, "max": 4.2}},
}

FIXED_PRESCRIBE_RESULT = {
    "battery_id": "B0005",
    "soh_percent": 82.0,
    "risk_level": "High",
    "priority": "P2",
    "action_code": "SCHEDULE_REPLACEMENT",
    "prescription": "Schedule replacement within 2 weeks.",
    "action_steps": ["Isolate string", "Order replacement"],
    "escalation_conditions": ["SOH < 80%"],
    "ppe_required": ["Insulated gloves"],
    "sop_references": ["SOP-BAT-07"],
    "enriched": False,
    "maintenance_docs": [],
    "safety_docs": [],
    "human_verification_required": True,
    "safety_warnings": ["High voltage"],
    "inference_ms": 15.0,
    "rag_ms": 0.0,
    "llm_ms": 0.0,
}


@pytest.fixture()
def dummy_models():
    scaler, feat_scaler, model, iso = make_dummy_loader()
    with (
        patch.object(model_loader, "scaler", scaler),
        patch.object(model_loader, "feature_scaler", feat_scaler),
        patch.object(model_loader, "soh_model", model),
        patch.object(model_loader, "iso_model", iso),
    ):
        yield


@pytest.fixture()
def servicer(dummy_models):
    return AiServiceServicer()


@pytest.fixture()
def grpc_stub(dummy_models):
    """Real in-process server on an OS-assigned port → real client stub."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    pb_grpc.add_AiServiceServicer_to_server(AiServiceServicer(), server)
    port = server.add_insecure_port("localhost:0")
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    yield pb_grpc.AiServiceStub(channel)
    channel.close()
    server.stop(grace=None)


@pytest.fixture()
def rest_client(dummy_models):
    with patch("src.core.model_loader.load_models"):
        from main import app

        with TestClient(app) as client:
            yield client


# ── Health ─────────────────────────────────────────────────────────────


def test_health(servicer):
    resp = servicer.Health(pb.HealthRequest(), None)
    assert resp.status == "ok"
    assert resp.model_version == MODEL_VERSION
    assert resp.scaler_loaded and resp.mamba_loaded and resp.isolation_forest_loaded


# ── Predict ────────────────────────────────────────────────────────────


def test_predict_returns_valid_response(servicer):
    resp = servicer.Predict(
        pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS), None
    )
    assert resp.battery_id == "B0005"
    assert resp.classification in ("Normal", "Degrading", "Failed")
    assert 0.0 <= resp.soh_percent <= 100.0
    assert 0.0 <= resp.confidence <= 1.0
    # nested mirrors flat compat fields
    assert resp.prediction.soh_percent == resp.soh_percent
    assert resp.metadata.window_size == WINDOW_SIZE
    assert len(resp.feature_summary) > 0


def test_predict_invalid_shape_aborts_invalid_argument(grpc_stub):
    short = [pb.Reading(values=[3.7] * BASE_N) for _ in range(5)]
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(pb.PredictRequest(battery_id="B0005", readings=short))
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "timesteps" in exc_info.value.details()


def test_predict_wrong_feature_count_aborts_invalid_argument(grpc_stub):
    bad = [pb.Reading(values=[3.7, 1.5]) for _ in range(WINDOW_SIZE)]
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(pb.PredictRequest(battery_id="B0005", readings=bad))
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


# ── reading_objects named-field parity (GH-77) ──────────────────────────


def test_predict_reading_objects_matches_readings_array(servicer):
    """gRPC named-field reading_objects must normalize to the exact same
    rows the equivalent array-format readings would send to run_inference()."""
    array_readings = [list(r.values) for r in VALID_READINGS]
    with patch(
        "src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT
    ) as mock_infer:
        servicer.Predict(
            pb.PredictRequest(battery_id="B0005", reading_objects=VALID_READING_FIELDS),
            None,
        )
    (object_call_readings,), _ = mock_infer.call_args
    assert object_call_readings == array_readings


def test_predict_reading_objects_6field_matches_readings_array(servicer):
    """Same parity check with cycle_count/soc_percent included."""
    array_readings = [list(r.values) for r in VALID_READINGS_6COL]
    with patch(
        "src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT
    ) as mock_infer:
        servicer.Predict(
            pb.PredictRequest(
                battery_id="B0005", reading_objects=VALID_READING_FIELDS_6COL
            ),
            None,
        )
    (object_call_readings,), _ = mock_infer.call_args
    assert object_call_readings == array_readings


def test_predict_reading_objects_matches_rest_object_format(servicer, rest_client):
    """gRPC reading_objects and REST object-format readings — same input
    logic, same normalized rows, across both transports."""
    rest_readings = [
        {
            "voltage": r.values[0],
            "current": r.values[1],
            "temperature": r.values[2],
            "time": r.values[3],
        }
        for r in VALID_READINGS
    ]
    with (
        patch(
            "src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT
        ) as grpc_mock,
        patch(
            "src.routers.predict.run_inference", return_value=FIXED_PREDICT_RESULT
        ) as rest_mock,
    ):
        rest_client.post(
            "/predict/", json={"battery_id": "B0005", "readings": rest_readings}
        )
        servicer.Predict(
            pb.PredictRequest(battery_id="B0005", reading_objects=VALID_READING_FIELDS),
            None,
        )
    (grpc_readings,), _ = grpc_mock.call_args
    (rest_readings_normalized,), _ = rest_mock.call_args
    assert grpc_readings == rest_readings_normalized


def test_predict_reading_objects_takes_precedence_over_readings(servicer):
    """If a client sends both readings and reading_objects (documented edge
    case, not a validation error), reading_objects wins."""
    array_readings = [list(r.values) for r in VALID_READINGS]
    with patch(
        "src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT
    ) as mock_infer:
        servicer.Predict(
            pb.PredictRequest(
                battery_id="B0005",
                readings=[
                    pb.Reading(values=[9.9] * BASE_N) for _ in range(WINDOW_SIZE)
                ],
                reading_objects=VALID_READING_FIELDS,
            ),
            None,
        )
    (used_readings,), _ = mock_infer.call_args
    assert used_readings == array_readings


# ── PredictStream (GH-41) ──────────────────────────────────────────────


class TestPredictStream:
    def test_n_windows_yield_n_predictions_in_order(self, grpc_stub):
        n = 5
        requests = [
            pb.PredictRequest(battery_id=f"B{i:04d}", readings=VALID_READINGS)
            for i in range(n)
        ]
        responses = list(grpc_stub.PredictStream(iter(requests)))
        assert len(responses) == n
        # battery_id echoes the request → proves response i belongs to request i
        assert [r.battery_id for r in responses] == [f"B{i:04d}" for i in range(n)]
        for r in responses:
            assert r.classification in ("Normal", "Degrading", "Failed")
            assert 0.0 <= r.soh_percent <= 100.0

    def test_stream_response_matches_unary(self, grpc_stub):
        """Same window through the stream and through unary Predict must give
        the identical message (fixed pipeline output — MC Dropout is stochastic)."""
        request = pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS)
        with patch("src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT):
            streamed = list(grpc_stub.PredictStream(iter([request])))
            unary = grpc_stub.Predict(request)
        assert len(streamed) == 1
        assert streamed[0] == unary

    def test_invalid_window_mid_stream_aborts_after_prior_responses(self, grpc_stub):
        bad = pb.PredictRequest(
            battery_id="B-bad",
            readings=[pb.Reading(values=[3.7] * BASE_N) for _ in range(5)],
        )
        requests = [
            pb.PredictRequest(battery_id="B0000", readings=VALID_READINGS),
            pb.PredictRequest(battery_id="B0001", readings=VALID_READINGS),
            bad,
            pb.PredictRequest(battery_id="B0003", readings=VALID_READINGS),
        ]
        received = []
        with pytest.raises(grpc.RpcError) as exc_info:
            for response in grpc_stub.PredictStream(iter(requests)):
                received.append(response.battery_id)
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
        # the two windows before the bad one were answered
        assert received == ["B0000", "B0001"]

    def test_empty_stream_returns_no_responses(self, grpc_stub):
        responses = list(grpc_stub.PredictStream(iter([])))
        assert responses == []

    def test_stream_accepts_reading_objects(self, grpc_stub):
        """GH-77 — PredictStream shares _predict_one() with unary Predict, so
        reading_objects must work per-window in the stream too, not just unary."""
        requests = [
            pb.PredictRequest(battery_id="B0000", reading_objects=VALID_READING_FIELDS),
            pb.PredictRequest(battery_id="B0001", readings=VALID_READINGS),
        ]
        responses = list(grpc_stub.PredictStream(iter(requests)))
        assert [r.battery_id for r in responses] == ["B0000", "B0001"]
        for r in responses:
            assert r.classification in ("Normal", "Degrading", "Failed")
            assert 0.0 <= r.soh_percent <= 100.0

    def test_client_cancel_mid_stream_leaves_server_usable(self, grpc_stub):
        def requests_forever():
            while True:
                yield pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS)

        call = grpc_stub.PredictStream(requests_forever())
        first = next(iter(call))
        assert first.battery_id == "B0005"
        call.cancel()
        # server must stay healthy after the cancelled stream
        health = grpc_stub.Health(pb.HealthRequest())
        assert health.status == "ok"

    def test_pipeline_error_mid_stream_aborts_internal(self, grpc_stub):
        request = pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS)
        with patch(
            "src.grpc_server.run_inference", side_effect=RuntimeError("model exploded")
        ):
            with pytest.raises(grpc.RpcError) as exc_info:
                list(grpc_stub.PredictStream(iter([request])))
        assert exc_info.value.code() == grpc.StatusCode.INTERNAL

    def test_concurrent_streams_do_not_mix_responses(self, grpc_stub):
        """Two interleaved streams on the same server (GH-42) — each client
        must get exactly its own battery_ids back, in its own order."""

        def run_stream(prefix: str) -> list[str]:
            requests = [
                pb.PredictRequest(battery_id=f"{prefix}-{i}", readings=VALID_READINGS)
                for i in range(3)
            ]
            return [r.battery_id for r in grpc_stub.PredictStream(iter(requests))]

        with futures.ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(run_stream, "A")
            future_b = pool.submit(run_stream, "B")
            ids_a, ids_b = future_a.result(timeout=120), future_b.result(timeout=120)

        assert ids_a == ["A-0", "A-1", "A-2"]
        assert ids_b == ["B-0", "B-1", "B-2"]


# ── Prescribe qua channel thật (GH-42) ─────────────────────────────────


def test_prescribe_via_channel_returns_valid_response(grpc_stub):
    """GH-40 covered Prescribe via direct servicer + parity; this exercises
    the full request path through a real channel with the dummy pipeline."""
    response = grpc_stub.Prescribe(
        pb.PrescribeRequest(battery_id="B0005", readings=VALID_READINGS, enrich=False)
    )
    assert response.battery_id == "B0005"
    assert response.risk_level in ("Critical", "High", "Medium", "Low")
    assert response.priority in ("P1", "P2", "P3", "None")
    assert response.prescription != ""
    assert len(response.action_steps) > 0
    assert response.enriched is False
    assert len(response.maintenance_docs) == 0  # empty unless enriched


# ── Parity with REST ───────────────────────────────────────────────────
# Both transports call the same pipeline; with run_inference patched to a
# fixed dict, gRPC and REST must serve identical payloads field-by-field.


def test_predict_parity_with_rest(servicer, rest_client):
    request_json = {
        "battery_id": "B0005",
        "readings": [list(r.values) for r in VALID_READINGS],
    }
    with (
        patch("src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT),
        patch("src.routers.predict.run_inference", return_value=FIXED_PREDICT_RESULT),
    ):
        rest = rest_client.post("/predict/", json=request_json).json()
        rpc = servicer.Predict(
            pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS), None
        )

    assert rpc.battery_id == rest["battery_id"]
    # flat compat fields
    for field in (
        "soh_percent",
        "classification",
        "confidence",
        "inference_ms",
        "rul_cycles_estimate",
        "degradation_rate_per_cycle",
        "soh_trend",
        "cycles_to_maintenance",
        "anomaly_score",
        "recommended_action",
    ):
        assert getattr(rpc, field) == rest[field], field
    assert list(rpc.soh_trajectory) == rest["soh_trajectory"]
    # nested blocks
    for field, rest_block in (
        ("prediction", rest["prediction"]),
        ("anomaly", rest["anomaly"]),
        ("risk", rest["risk"]),
        ("metadata", rest["metadata"]),
    ):
        rpc_block = getattr(rpc, field)
        for key, value in rest_block.items():
            rpc_value = getattr(rpc_block, key)
            if isinstance(value, list) and not isinstance(value, str):
                rpc_value = list(rpc_value)
            elif isinstance(value, dict):
                # proto map fields (GH-86 stage_probabilities) → plain dict
                rpc_value = dict(rpc_value)
            assert rpc_value == value, f"{field}.{key}"
    # warnings + feature_summary (flat and nested)
    for rpc_w, rest_w in zip(rpc.warnings, rest["warnings"], strict=True):
        assert (rpc_w.code, rpc_w.severity, rpc_w.message) == (
            rest_w["code"],
            rest_w["severity"],
            rest_w["message"],
        )
    for name, stat in rest["feature_summary"].items():
        assert rpc.feature_summary[name].mean == stat["mean"]
        assert rpc.feature_summary[name].min == stat["min"]
        assert rpc.feature_summary[name].max == stat["max"]
        assert rpc.evidence.feature_summary[name].mean == stat["mean"]


def test_predict_6col_parity_with_rest(servicer, rest_client):
    """GH-56 — payload 6-cot (BE tinh cycle_count/soc_percent) duoc validate va
    chuyen thang toi run_inference() giong het nhau tren ca 2 transport."""
    request_json = {
        "battery_id": "B0005",
        "readings": [list(r.values) for r in VALID_READINGS_6COL],
    }
    with (
        patch(
            "src.grpc_server.run_inference", return_value=FIXED_PREDICT_RESULT
        ) as grpc_mock,
        patch(
            "src.routers.predict.run_inference", return_value=FIXED_PREDICT_RESULT
        ) as rest_mock,
    ):
        rest = rest_client.post("/predict/", json=request_json).json()
        rpc = servicer.Predict(
            pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS_6COL), None
        )

    assert rpc.battery_id == rest["battery_id"] == "B0005"
    assert rpc.soh_percent == rest["soh_percent"] == FIXED_PREDICT_RESULT["soh_percent"]

    # both transports must parse the SAME 6-column readings before calling run_inference
    (grpc_readings,), _ = grpc_mock.call_args
    (rest_readings,), _ = rest_mock.call_args
    assert grpc_readings == rest_readings
    assert len(grpc_readings) == WINDOW_SIZE
    assert all(len(row) == BASE_N + 2 for row in grpc_readings)
    assert grpc_readings[0][4] == 42.0  # cycle_count, raw
    assert grpc_readings[0][5] == 100.0  # soc_percent, raw


def test_prescribe_parity_with_rest(servicer, rest_client):
    request_json = {
        "battery_id": "B0005",
        "readings": [list(r.values) for r in VALID_READINGS],
        "enrich": False,
    }
    with (
        patch("src.grpc_server.run_prescription", return_value=FIXED_PRESCRIBE_RESULT),
        patch(
            "src.routers.prescribe.run_prescription",
            return_value=FIXED_PRESCRIBE_RESULT,
        ),
    ):
        rest = rest_client.post("/prescribe/", json=request_json).json()
        rpc = servicer.Prescribe(
            pb.PrescribeRequest(
                battery_id="B0005", readings=VALID_READINGS, enrich=False
            ),
            None,
        )

    for field in (
        "battery_id",
        "soh_percent",
        "risk_level",
        "priority",
        "action_code",
        "prescription",
        "enriched",
        "human_verification_required",
        "inference_ms",
        "rag_ms",
        "llm_ms",
    ):
        assert getattr(rpc, field) == rest[field], field
    for field in (
        "action_steps",
        "escalation_conditions",
        "ppe_required",
        "sop_references",
        "safety_warnings",
    ):
        assert list(getattr(rpc, field)) == rest[field], field
    assert len(rpc.maintenance_docs) == len(rest["maintenance_docs"]) == 0


def test_prescribe_forwards_optional_context(servicer):
    """proto3 optional fields reach run_prescription only when set."""
    with patch(
        "src.grpc_server.run_prescription", return_value=FIXED_PRESCRIBE_RESULT
    ) as mock_run:
        servicer.Prescribe(
            pb.PrescribeRequest(
                battery_id="B0005",
                readings=VALID_READINGS,
                age_cycles=300,
                ticket_history=["T-1"],
            ),
            None,
        )
    kwargs = mock_run.call_args.kwargs
    assert kwargs["age_cycles"] == 300
    assert kwargs["last_maintenance_date"] is None  # not set → Pydantic default
    assert kwargs["ticket_history"] == ["T-1"]
    assert kwargs["enrich"] is False

    with patch(
        "src.grpc_server.run_prescription", return_value=FIXED_PRESCRIBE_RESULT
    ) as mock_run:
        servicer.Prescribe(
            pb.PrescribeRequest(
                battery_id="B0005",
                readings=VALID_READINGS,
                last_maintenance_date="2026-05-01",
            ),
            None,
        )
    assert mock_run.call_args.kwargs["last_maintenance_date"] == "2026-05-01"


# ── Error paths (INTERNAL) ─────────────────────────────────────────────


def test_predict_pipeline_error_aborts_internal(grpc_stub):
    with patch(
        "src.grpc_server.run_inference", side_effect=RuntimeError("model exploded")
    ):
        with pytest.raises(grpc.RpcError) as exc_info:
            grpc_stub.Predict(
                pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS)
            )
    assert exc_info.value.code() == grpc.StatusCode.INTERNAL
    assert "inference failed" in exc_info.value.details()


def test_prescribe_pipeline_error_aborts_internal(grpc_stub):
    with patch(
        "src.grpc_server.run_prescription", side_effect=RuntimeError("rag down")
    ):
        with pytest.raises(grpc.RpcError) as exc_info:
            grpc_stub.Prescribe(
                pb.PrescribeRequest(battery_id="B0005", readings=VALID_READINGS)
            )
    assert exc_info.value.code() == grpc.StatusCode.INTERNAL
    assert "prescription failed" in exc_info.value.details()


# ── Entrypoint ─────────────────────────────────────────────────────────


def test_create_server_binds_and_serves(dummy_models):
    from src.grpc_server import create_server

    server = create_server(port=0)  # OS-assigned port — no fixed-port collision
    server.start()
    server.stop(grace=None)


# ── Latency ────────────────────────────────────────────────────────────


def test_predict_grpc_transport_overhead(grpc_stub, dummy_models):
    """GH-40 adds only the gRPC transport on top of run_inference — the
    pipeline's own <100ms SLA is enforced by tests/test_prescription.py
    (and is CPU-borderline on dev machines, see commit 9b41269). Here we
    assert the transport layer stays cheap and the end-to-end call stays
    within the P2/P3 batch tier (<500ms, rules/tech/ai.md)."""
    from src.services.inference import run_inference

    readings_lists = [list(r.values) for r in VALID_READINGS]
    request = pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS)

    run_inference(readings_lists)  # warm-up
    grpc_stub.Predict(request)  # warm-up

    direct, end_to_end = [], []
    for _ in range(20):
        start = time.perf_counter()
        run_inference(readings_lists)
        direct.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        grpc_stub.Predict(request)
        end_to_end.append((time.perf_counter() - start) * 1000)

    direct_avg = sum(direct) / len(direct)
    grpc_avg = sum(end_to_end) / len(end_to_end)
    overhead = grpc_avg - direct_avg
    print(
        f"[GH-40] Predict latency: direct {direct_avg:.1f}ms | "
        f"gRPC {grpc_avg:.1f}ms | transport overhead {overhead:.1f}ms"
    )
    assert overhead < 50, f"gRPC transport overhead too high: {overhead:.1f}ms >= 50ms"
    assert grpc_avg < 500, f"gRPC Predict too slow: {grpc_avg:.1f}ms >= 500ms"


# ── pack_config pack→cell (GH-65) + range guard (GH-66) ─────────────────

_12V_READINGS = [
    pb.Reading(values=[r.values[0] * 3, r.values[1], r.values[2], r.values[3]])
    for r in VALID_READINGS
]


def test_predict_12v_without_pack_config_aborts_with_hint(grpc_stub):
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(pb.PredictRequest(battery_id="PACK", readings=_12V_READINGS))
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "pack_config" in exc_info.value.details()


def test_predict_12v_with_n_series_3_ok_and_traced(servicer):
    resp = servicer.Predict(
        pb.PredictRequest(
            battery_id="PACK",
            readings=_12V_READINGS,
            pack_config=pb.PackConfig(n_series=3, chemistry="NMC"),
        ),
        None,
    )
    assert resp.metadata.n_series == 3
    assert 0.0 <= resp.soh_percent <= 100.0
    # per-cell voltage back in the trained range → no OVERVOLTAGE false alarm
    assert not any("OVERVOLTAGE" in w.code for w in resp.evidence.warnings)


# ── temperature domain distance / OOD flag (GH-91) ──────────────────────

_TEMP_OOD_READINGS = [
    pb.Reading(values=[r.values[0], r.values[1], 15.0, r.values[3]])
    for r in VALID_READINGS
]


def test_predict_temperature_ood_flagged_via_grpc(servicer):
    """15°C — issue #91's motivating example: 9°C from nearest cluster (24°C),
    beyond TEMPERATURE_OOD_THRESHOLD (5°C) — must be flagged on the production
    (gRPC) transport."""
    resp = servicer.Predict(
        pb.PredictRequest(battery_id="B0005", readings=_TEMP_OOD_READINGS), None
    )
    assert resp.metadata.is_temperature_ood is True
    assert resp.metadata.temperature_domain_distance == 9.0
    assert any(w.code == "TEMP_OOD" for w in resp.evidence.warnings)


def test_predict_pack_config_chemistry_only_defaults_n_series_1(servicer):
    """proto3: n_series unset (0) inside a set pack_config → treated as 1."""
    resp = servicer.Predict(
        pb.PredictRequest(
            battery_id="B0005",
            readings=VALID_READINGS,
            pack_config=pb.PackConfig(chemistry="NMC"),
        ),
        None,
    )
    assert resp.metadata.n_series == 1


def test_predict_out_of_range_parity_with_rest(grpc_stub, rest_client):
    """GH-66 parity: the same violating payload → REST 422, gRPC INVALID_ARGUMENT,
    both naming the offending field."""
    bad_rows = [list(r.values) for r in VALID_READINGS]
    bad_rows[3][2] = 75.0  # temperature above 60°C ceiling
    rest_resp = rest_client.post(
        "/predict/", json={"battery_id": "B0005", "readings": bad_rows}
    )
    assert rest_resp.status_code == 422
    assert "temperature" in str(rest_resp.json())
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(
            pb.PredictRequest(
                battery_id="B0005",
                readings=[pb.Reading(values=r) for r in bad_rows],
            )
        )
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "temperature" in exc_info.value.details()


def test_predict_nan_aborts_invalid_argument(grpc_stub):
    rows = [list(r.values) for r in VALID_READINGS]
    rows[0][0] = float("nan")
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(
            pb.PredictRequest(
                battery_id="B0005", readings=[pb.Reading(values=r) for r in rows]
            )
        )
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "NaN" in exc_info.value.details()


def test_prescribe_forwards_pack_config(servicer):
    with patch(
        "src.grpc_server.run_prescription", return_value=FIXED_PRESCRIBE_RESULT
    ) as mock_rx:
        servicer.Prescribe(
            pb.PrescribeRequest(
                battery_id="PACK",
                readings=_12V_READINGS,
                pack_config=pb.PackConfig(n_series=3),
            ),
            None,
        )
    assert mock_rx.call_args.kwargs["n_series"] == 3
