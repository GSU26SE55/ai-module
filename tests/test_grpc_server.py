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
from src.core.config import INPUT_FEATURES, MODEL_VERSION, WINDOW_SIZE
from src.grpc_gen import ai_service_pb2 as pb
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc
from src.grpc_server import AiServiceServicer
from tests.test_routers import make_dummy_loader

VALID_READINGS = [
    pb.Reading(values=np.random.RandomState(42).rand(INPUT_FEATURES).tolist())
    for _ in range(WINDOW_SIZE)
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
    short = [pb.Reading(values=[3.7] * INPUT_FEATURES) for _ in range(5)]
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(pb.PredictRequest(battery_id="B0005", readings=short))
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "timesteps" in exc_info.value.details()


def test_predict_wrong_feature_count_aborts_invalid_argument(grpc_stub):
    bad = [pb.Reading(values=[3.7, 1.5]) for _ in range(WINDOW_SIZE)]
    with pytest.raises(grpc.RpcError) as exc_info:
        grpc_stub.Predict(pb.PredictRequest(battery_id="B0005", readings=bad))
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT


def test_predict_stream_unimplemented(grpc_stub):
    with pytest.raises(grpc.RpcError) as exc_info:
        list(
            grpc_stub.PredictStream(
                iter([pb.PredictRequest(battery_id="B0005", readings=VALID_READINGS)])
            )
        )
    assert exc_info.value.code() == grpc.StatusCode.UNIMPLEMENTED


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
