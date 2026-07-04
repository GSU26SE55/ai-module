"""
GH-39 — gRPC contract tests: generated stubs import, message round-trip,
and field-name parity between proto messages and the REST Pydantic schemas.

No server here (that's GH-40/41) — only the contract itself.
"""

import pytest

from src.grpc_gen import ai_service_pb2 as pb
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc
from src.schemas.predict import (
    AnomalyInfo,
    FeatureStat,
    PredictionInfo,
    PredictRequest,
    PredictResponse,
    ResponseMetadata,
    RiskInfo,
    WarningItem,
)
from src.schemas.prescribe import PrescribeRequest, PrescribeResponse, RetrievedDoc


def proto_field_names(message_cls) -> set[str]:
    return {f.name for f in message_cls.DESCRIPTOR.fields}


def pydantic_field_names(model_cls) -> set[str]:
    return set(model_cls.model_fields.keys())


# ── Import & service surface ───────────────────────────────────────────


def test_stub_modules_importable():
    assert hasattr(pb_grpc, "AiServiceStub")
    assert hasattr(pb_grpc, "AiServiceServicer")
    assert hasattr(pb_grpc, "add_AiServiceServicer_to_server")


def test_service_defines_expected_methods():
    service = pb.DESCRIPTOR.services_by_name["AiService"]
    methods = {m.name: m for m in service.methods}
    assert set(methods) == {"Predict", "Prescribe", "Health", "PredictStream"}

    stream = methods["PredictStream"]
    assert stream.client_streaming and stream.server_streaming
    for name in ("Predict", "Prescribe", "Health"):
        assert not methods[name].client_streaming
        assert not methods[name].server_streaming


# ── Round-trip ─────────────────────────────────────────────────────────


def test_predict_request_round_trip():
    req = pb.PredictRequest(
        battery_id="B0005",
        readings=[pb.Reading(values=[3.7, 1.5, 25.0]) for _ in range(30)],
    )
    parsed = pb.PredictRequest.FromString(req.SerializeToString())
    assert parsed == req
    assert parsed.battery_id == "B0005"
    assert len(parsed.readings) == 30
    assert list(parsed.readings[0].values) == [3.7, 1.5, 25.0]


def test_predict_response_round_trip():
    resp = pb.PredictResponse(
        battery_id="B0005",
        prediction=pb.PredictionInfo(
            soh_percent=87.5,
            soh_confidence=0.92,
            soh_std=1.3,
            rul_cycles_estimate=120,
            degradation_rate_per_cycle=0.15,
            soh_trend="stable",
            cycles_to_maintenance=17,
            soh_trajectory=[87.5, 87.35, 87.2, 87.05, 86.9],
            health_stage="mid-life",
        ),
        anomaly=pb.AnomalyInfo(
            anomaly_score=-0.05, anomaly_status="Normal", anomaly_confidence=0.05
        ),
        risk=pb.RiskInfo(
            risk_level="Low",
            priority="P3",
            action_code="MONITOR",
            reasons=["SOH healthy"],
        ),
        evidence=pb.EvidenceInfo(
            warnings=[
                pb.WarningItem(code="SOH_LOW", severity="warning", message="watch")
            ],
            feature_summary={"voltage": pb.FeatureStat(mean=3.7, min=3.2, max=4.2)},
        ),
        metadata=pb.ResponseMetadata(
            model_version="1.0", window_size=30, input_features=6, inference_ms=12.3
        ),
        soh_percent=87.5,
        classification="Normal",
        confidence=0.05,
        inference_ms=12.3,
        rul_cycles_estimate=120,
        degradation_rate_per_cycle=0.15,
        soh_trend="stable",
        cycles_to_maintenance=17,
        soh_trajectory=[87.5, 87.35, 87.2, 87.05, 86.9],
        anomaly_score=-0.05,
        recommended_action="MONITOR",
        warnings=[pb.WarningItem(code="SOH_LOW", severity="warning", message="watch")],
        feature_summary={"voltage": pb.FeatureStat(mean=3.7, min=3.2, max=4.2)},
    )
    parsed = pb.PredictResponse.FromString(resp.SerializeToString())
    assert parsed == resp
    assert parsed.prediction.soh_percent == 87.5
    assert parsed.evidence.feature_summary["voltage"].max == 4.2
    assert parsed.soh_percent == parsed.prediction.soh_percent


def test_prescribe_round_trip_with_optional_fields():
    req = pb.PrescribeRequest(
        battery_id="B0005",
        readings=[pb.Reading(values=[3.7, 1.5, 25.0]) for _ in range(30)],
        age_cycles=300,
        ticket_history=["T-1", "T-2"],
        enrich=True,
    )
    parsed = pb.PrescribeRequest.FromString(req.SerializeToString())
    assert parsed == req
    assert parsed.HasField("age_cycles") and parsed.age_cycles == 300
    assert not parsed.HasField("last_maintenance_date")

    resp = pb.PrescribeResponse(
        battery_id="B0005",
        soh_percent=82.0,
        risk_level="High",
        priority="P2",
        action_code="SCHEDULE_REPLACEMENT",
        prescription="Schedule replacement within 2 weeks.",
        action_steps=["Isolate string", "Order replacement"],
        escalation_conditions=["SOH < 80%"],
        ppe_required=["Insulated gloves"],
        sop_references=["SOP-BAT-07"],
        enriched=True,
        maintenance_docs=[
            pb.RetrievedDoc(
                title="BMS codes",
                content="...",
                source="maintenance/bms_warning_codes.md",
                relevance_score=0.87,
            )
        ],
        human_verification_required=True,
        safety_warnings=["High voltage"],
        inference_ms=15.0,
        rag_ms=120.0,
        llm_ms=800.0,
    )
    parsed_resp = pb.PrescribeResponse.FromString(resp.SerializeToString())
    assert parsed_resp == resp
    assert parsed_resp.maintenance_docs[0].relevance_score == 0.87


def test_health_response_round_trip():
    resp = pb.HealthResponse(
        status="ok",
        model_version="1.0",
        scaler_loaded=True,
        mamba_loaded=True,
        isolation_forest_loaded=True,
    )
    parsed = pb.HealthResponse.FromString(resp.SerializeToString())
    assert parsed == resp


# ── Field parity with Pydantic schemas ─────────────────────────────────
# Proto messages must expose every field the REST schema exposes, with the
# same names, so BE can migrate REST → gRPC without remapping payloads.
# PredictRequest is exempt from exact equality: REST uses list[list[float]],
# proto wraps rows in Reading.

PARITY_CASES = [
    (WarningItem, pb.WarningItem),
    (FeatureStat, pb.FeatureStat),
    (PredictionInfo, pb.PredictionInfo),
    (AnomalyInfo, pb.AnomalyInfo),
    (RiskInfo, pb.RiskInfo),
    (ResponseMetadata, pb.ResponseMetadata),
    (RetrievedDoc, pb.RetrievedDoc),
    (PrescribeRequest, pb.PrescribeRequest),
    (PrescribeResponse, pb.PrescribeResponse),
]


@pytest.mark.parametrize(
    "pydantic_cls,proto_cls", PARITY_CASES, ids=[p.__name__ for p, _ in PARITY_CASES]
)
def test_field_names_match_pydantic(pydantic_cls, proto_cls):
    assert proto_field_names(proto_cls) == pydantic_field_names(pydantic_cls)


def test_predict_request_fields():
    # GH-77: `reading_objects` is proto-only — it maps onto the Pydantic
    # `readings` Union (list[list[float]] | list[ReadingObject]), not a
    # separate named field, so it's excluded from the exact-match set.
    assert proto_field_names(pb.PredictRequest) - {
        "reading_objects"
    } == pydantic_field_names(PredictRequest)


def test_predict_response_covers_all_pydantic_fields():
    assert proto_field_names(pb.PredictResponse) == pydantic_field_names(
        PredictResponse
    )
