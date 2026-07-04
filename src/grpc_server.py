"""
gRPC server — GH-40. Serves the aimodule.v1.AiService contract (GH-39)
alongside FastAPI (hybrid): same inference/prescription pipeline, separate
process on GRPC_PORT (default 50051).

Run:  python -m src.grpc_server

Only the unary RPCs (Predict, Prescribe, Health) are implemented here;
PredictStream inherits UNIMPLEMENTED from the base servicer (GH-41).
"""

import logging
import os
from concurrent import futures

import grpc
from pydantic import ValidationError

from src.core import model_loader
from src.core.config import MODEL_VERSION
from src.grpc_gen import ai_service_pb2, ai_service_pb2_grpc
from src.schemas.predict import PredictRequest
from src.schemas.prescribe import PrescribeRequest
from src.services.inference import run_inference
from src.services.prescription import run_prescription

logger = logging.getLogger(__name__)

MAX_WORKERS = 10
DEFAULT_PORT = 50051


# ── dict → proto mapping ───────────────────────────────────────────────
# run_inference() / run_prescription() return PredictResponse /
# PrescribeResponse-compatible dicts (nested + flat compat fields) —
# the same payloads FastAPI serves. Map them 1:1 onto the proto messages.


def _pack_config_dict(pack_config) -> dict:
    """GH-65: proto PackConfig → dict for the shared Pydantic schema.

    proto3 scalar semantics: n_series=0 means "not set" → treat as 1 (single
    cell) instead of failing the ge=1 constraint, so `pack_config {chemistry:
    "NMC"}` behaves like REST's `{"chemistry": "NMC"}` (n_series defaults)."""
    return {
        "n_series": pack_config.n_series or 1,
        "chemistry": pack_config.chemistry or None,
    }


def _to_warning_items(warnings: list[dict]) -> list[ai_service_pb2.WarningItem]:
    return [
        ai_service_pb2.WarningItem(
            code=w["code"], severity=w["severity"], message=w["message"]
        )
        for w in warnings
    ]


def _fill_feature_summary(field, feature_summary: dict) -> None:
    """Fill a map<string, FeatureStat> field from {name: {mean,min,max}}."""
    for name, stat in feature_summary.items():
        field[name].mean = stat["mean"]
        field[name].min = stat["min"]
        field[name].max = stat["max"]


def _to_predict_response(
    battery_id: str, result: dict
) -> ai_service_pb2.PredictResponse:
    prediction = result["prediction"]
    anomaly = result["anomaly"]
    risk = result["risk"]
    evidence = result["evidence"]
    metadata = result["metadata"]

    response = ai_service_pb2.PredictResponse(
        battery_id=battery_id,
        prediction=ai_service_pb2.PredictionInfo(
            soh_percent=prediction["soh_percent"],
            soh_confidence=prediction["soh_confidence"],
            soh_std=prediction["soh_std"],
            rul_cycles_estimate=prediction["rul_cycles_estimate"],
            degradation_rate_per_cycle=prediction["degradation_rate_per_cycle"],
            soh_trend=prediction["soh_trend"],
            cycles_to_maintenance=prediction["cycles_to_maintenance"],
            soh_trajectory=prediction["soh_trajectory"],
            health_stage=prediction["health_stage"],
        ),
        anomaly=ai_service_pb2.AnomalyInfo(
            anomaly_score=anomaly["anomaly_score"],
            anomaly_status=anomaly["anomaly_status"],
            anomaly_confidence=anomaly["anomaly_confidence"],
        ),
        risk=ai_service_pb2.RiskInfo(
            risk_level=risk["risk_level"],
            priority=risk["priority"],
            action_code=risk["action_code"],
            reasons=risk["reasons"],
        ),
        evidence=ai_service_pb2.EvidenceInfo(
            warnings=_to_warning_items(evidence["warnings"]),
        ),
        metadata=ai_service_pb2.ResponseMetadata(
            model_version=metadata["model_version"],
            window_size=metadata["window_size"],
            input_features=metadata["input_features"],
            inference_ms=metadata["inference_ms"],
            n_series=metadata["n_series"],
        ),
        # Flat backward-compat fields — identical to the REST payload
        soh_percent=result["soh_percent"],
        classification=result["classification"],
        confidence=result["confidence"],
        inference_ms=result["inference_ms"],
        rul_cycles_estimate=result["rul_cycles_estimate"],
        degradation_rate_per_cycle=result["degradation_rate_per_cycle"],
        soh_trend=result["soh_trend"],
        cycles_to_maintenance=result["cycles_to_maintenance"],
        soh_trajectory=result["soh_trajectory"],
        anomaly_score=result["anomaly_score"],
        recommended_action=result["recommended_action"],
        warnings=_to_warning_items(result["warnings"]),
    )
    _fill_feature_summary(
        response.evidence.feature_summary, evidence["feature_summary"]
    )
    _fill_feature_summary(response.feature_summary, result["feature_summary"])
    return response


def _to_retrieved_docs(docs: list[dict]) -> list[ai_service_pb2.RetrievedDoc]:
    return [
        ai_service_pb2.RetrievedDoc(
            title=d["title"],
            content=d["content"],
            source=d["source"],
            relevance_score=d["relevance_score"],
        )
        for d in docs
    ]


def _to_prescribe_response(result: dict) -> ai_service_pb2.PrescribeResponse:
    return ai_service_pb2.PrescribeResponse(
        battery_id=result["battery_id"],
        soh_percent=result["soh_percent"],
        risk_level=result["risk_level"],
        priority=result["priority"],
        action_code=result["action_code"],
        prescription=result["prescription"],
        action_steps=result["action_steps"],
        escalation_conditions=result["escalation_conditions"],
        ppe_required=result["ppe_required"],
        sop_references=result["sop_references"],
        enriched=result["enriched"],
        maintenance_docs=_to_retrieved_docs(result["maintenance_docs"]),
        safety_docs=_to_retrieved_docs(result["safety_docs"]),
        human_verification_required=result["human_verification_required"],
        safety_warnings=result["safety_warnings"],
        inference_ms=result["inference_ms"],
        rag_ms=result["rag_ms"],
        llm_ms=result["llm_ms"],
    )


# ── Servicer ───────────────────────────────────────────────────────────


class AiServiceServicer(ai_service_pb2_grpc.AiServiceServicer):
    """RPCs backed by the same pipeline FastAPI serves."""

    def _predict_one(self, request, context) -> ai_service_pb2.PredictResponse:
        """Shared unary/stream path: validate → run_inference → map to proto."""
        if request.reading_objects:
            # GH-77: named-field format — takes precedence over `readings`,
            # mirrors REST's Union-type acceptance. Built as dicts so the
            # SAME Pydantic schema (ReadingObject) validates/normalizes them,
            # no separate gRPC-only logic.
            readings = [
                {
                    "voltage": r.voltage,
                    "current": r.current,
                    "temperature": r.temperature,
                    "time": r.time,
                    **(
                        {"cycle_count": r.cycle_count}
                        if r.HasField("cycle_count")
                        else {}
                    ),
                    **(
                        {"soc_percent": r.soc_percent}
                        if r.HasField("soc_percent")
                        else {}
                    ),
                }
                for r in request.reading_objects
            ]
        else:
            readings = [list(r.values) for r in request.readings]
        payload = {"battery_id": request.battery_id, "readings": readings}
        if request.HasField("pack_config"):
            payload["pack_config"] = _pack_config_dict(request.pack_config)
        parsed = _validate(PredictRequest, payload, context)
        n_series = parsed.pack_config.n_series if parsed.pack_config else 1
        try:
            result = run_inference(parsed.readings, n_series=n_series)
        except Exception as exc:
            logger.exception("Predict failed")
            context.abort(grpc.StatusCode.INTERNAL, f"inference failed: {exc}")
        return _to_predict_response(parsed.battery_id, result)

    def Predict(self, request, context):
        return self._predict_one(request, context)

    def Prescribe(self, request, context):
        payload = {
            "battery_id": request.battery_id,
            "readings": [list(r.values) for r in request.readings],
            "ticket_history": list(request.ticket_history),
            "enrich": request.enrich,
        }
        # proto3 optional → only forward when explicitly set (Pydantic defaults otherwise)
        if request.HasField("age_cycles"):
            payload["age_cycles"] = request.age_cycles
        if request.HasField("last_maintenance_date"):
            payload["last_maintenance_date"] = request.last_maintenance_date
        if request.HasField("pack_config"):
            payload["pack_config"] = _pack_config_dict(request.pack_config)
        parsed = _validate(PrescribeRequest, payload, context)
        try:
            result = run_prescription(
                readings=parsed.readings,
                battery_id=parsed.battery_id,
                enrich=parsed.enrich,
                n_series=parsed.pack_config.n_series if parsed.pack_config else 1,
                age_cycles=parsed.age_cycles,
                last_maintenance_date=parsed.last_maintenance_date,
                ticket_history=parsed.ticket_history,
            )
        except Exception as exc:
            logger.exception("Prescribe failed")
            context.abort(grpc.StatusCode.INTERNAL, f"prescription failed: {exc}")
        return _to_prescribe_response(result)

    def PredictStream(self, request_iterator, context):
        """Bidirectional streaming Predict (GH-41) — sensor real-time.

        Each streamed PredictRequest is one full 30-timestep window and goes
        through the exact unary path (validate → run_inference → map), so a
        stream of N windows yields N responses in request order. Ordering is
        guaranteed by sequential processing in this handler thread; back-
        pressure comes from gRPC/HTTP/2 flow control on request_iterator.

        Error semantics: gRPC bidi has no per-message error channel — an
        invalid window aborts the stream with INVALID_ARGUMENT after the
        client has received responses for all prior windows.
        """
        for request in request_iterator:
            yield self._predict_one(request, context)

    def Health(self, request, context):
        return ai_service_pb2.HealthResponse(
            status="ok",
            model_version=MODEL_VERSION,
            scaler_loaded=model_loader.scaler is not None,
            mamba_loaded=model_loader.soh_model is not None,
            isolation_forest_loaded=model_loader.iso_model is not None,
        )


def _validate(schema_cls, payload: dict, context):
    """Validate a request payload with the REST Pydantic schema.

    Reuses the exact validators FastAPI runs (window size, feature counts),
    so both transports reject the same inputs. Aborts with INVALID_ARGUMENT
    on validation failure (context.abort raises — no return after it).
    """
    try:
        return schema_cls(**payload)
    except ValidationError as exc:
        context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))


# ── Entrypoint ─────────────────────────────────────────────────────────


def create_server(port: int, max_workers: int = MAX_WORKERS) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    ai_service_pb2_grpc.add_AiServiceServicer_to_server(AiServiceServicer(), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    return server


def serve() -> None:
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("GRPC_PORT", DEFAULT_PORT))
    model_loader.load_models()  # once at startup, like the FastAPI lifespan
    server = create_server(port)
    server.start()
    logger.info("gRPC server listening on port %d (model %s)", port, MODEL_VERSION)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
