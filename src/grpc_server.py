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
from src.core.config import LFP_MODEL_VERSION, LONG_MODEL_VERSION, MODEL_VERSION
from src.grpc_gen import ai_service_pb2, ai_service_pb2_grpc
from src.schemas.predict import (
    ClassificationFeedbackRequest,
    PredictLongRequest,
    PredictRequest,
)
from src.schemas.prescribe import PrescribeRequest, PrescriptionFeedbackRequest
from src.schemas.suggest import SuggestKbRequest, SuggestStaffRequest
from src.schemas.verify import VerifyTicketRequest
from src.services.classification_feedback import record_feedback
from src.services.inference import predict_soh_long, run_inference, soc_mode_for
from src.services.prescription import run_prescription, submit_prescription_feedback
from src.services.suggest_kb import run_suggest_kb
from src.services.suggest_staff import run_suggest_staff
from src.services.verify import run_verify

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
    "NMC"}` behaves like REST's `{"chemistry": "NMC"}` (n_series defaults).
    GH-67: capacity_ah=0.0 likewise means "not set" → None (no C-rate rescale,
    and it would fail the gt=0 constraint otherwise)."""
    return {
        "n_series": pack_config.n_series or 1,
        "chemistry": pack_config.chemistry or None,
        "capacity_ah": pack_config.capacity_ah or None,
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
            stage_probabilities=prediction["stage_probabilities"],
            stage_confidence=prediction["stage_confidence"],
            is_borderline=prediction["is_borderline"],
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
            temperature_domain_distance=metadata["temperature_domain_distance"],
            is_temperature_ood=metadata["is_temperature_ood"],
            # GH-67: None → proto3 defaults ("" / 0.0) = NASA/NMC defaults applied
            chemistry=metadata["chemistry"] or "",
            capacity_ah=metadata["capacity_ah"] or 0.0,
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
            retrieved_via=d.get("retrieved_via", ""),
        )
        for d in docs
    ]


def _to_prescribe_response(result: dict) -> ai_service_pb2.PrescribeResponse:
    prediction = result["prediction"]
    anomaly = result["anomaly"]
    risk = result["risk"]
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
        llm_provider=result["llm_provider"],
        blocked=result.get("blocked", False),
        cached=result.get("cached", False),
        query_gen_ms=result.get("query_gen_ms", 0.0),
        generated_queries=result.get("generated_queries", []),
        prescription_id=result.get("prescription_id", ""),
        # GH-87: nested prediction/anomaly/risk — same mapping as _to_predict_response.
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
            stage_probabilities=prediction["stage_probabilities"],
            stage_confidence=prediction["stage_confidence"],
            is_borderline=prediction["is_borderline"],
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
        pack = parsed.pack_config
        try:
            result = run_inference(
                parsed.readings,
                n_series=pack.n_series if pack else 1,
                chemistry=pack.chemistry if pack else None,
                capacity_ah=pack.capacity_ah if pack else None,
                battery_id=parsed.battery_id,
            )
        except ValueError as exc:
            # Payload sai hình dạng so với bộ artifact được chọn — điển hình là gửi 4 cột
            # cho bộ soc_mode="cycle". Đây là lỗi của INPUT, không phải server hỏng.
            # Trả INTERNAL khiến caller tưởng AI chết rồi fallback sang HTTP, nơi cùng một
            # payload bị từ chối y hệt: tốn hai round-trip để nhận cùng một câu trả lời.
            # INVALID_ARGUMENT cho caller dừng ngay và sửa payload.
            logger.warning("Predict rejected payload: %s", exc)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
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
            "agentic": request.agentic,
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
                # GH-67: same pack_config forwarding as REST — parity is enforced
                # by tests/test_grpc_server.py.
                chemistry=parsed.pack_config.chemistry if parsed.pack_config else None,
                capacity_ah=parsed.pack_config.capacity_ah if parsed.pack_config else None,
                agentic=parsed.agentic,
                age_cycles=parsed.age_cycles,
                last_maintenance_date=parsed.last_maintenance_date,
                ticket_history=parsed.ticket_history,
            )
        except ValueError as exc:
            # Cùng lý do như Predict: Prescribe chạy run_inference() làm bước 1, nên nó
            # thừa hưởng y hệt lỗi payload-vs-artifact. Phải phân loại giống nhau, nếu
            # không cùng một payload sai lại cho hai mã lỗi khác nhau tuỳ RPC.
            logger.warning("Prescribe rejected payload: %s", exc)
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
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
            # GH-67: parity with REST /health — BE checks these before routing
            # any chemistry="LFP" traffic (that request fails if not loaded).
            lfp_loaded=model_loader.lfp_soh_model is not None,
            lfp_model_version=LFP_MODEL_VERSION,
            # soc_mode belongs to the ARTIFACTS, not the request. Callers that
            # hardcode it by chemistry break silently the day a set is retrained
            # with the other definition — a wrong soc_percent is never rejected.
            soc_mode=soc_mode_for(None),
            lfp_soc_mode=soc_mode_for("LFP"),
            # Long model loads LAZILY on first PredictLong, so False here means
            # "not called yet", NOT "artifact missing".
            long_loaded=model_loader.long_soh_model is not None,
            long_model_version=LONG_MODEL_VERSION,
        )

    def PredictLong(self, request, context):
        """SOH from a long raw series (31..4096). Mirror of POST /predict/long.

        SOH only — no MC-dropout and no IsolationForest on this path (the forest
        is fitted on the window=30 feature distribution). Validated through the
        SAME Pydantic schema as REST so both transports reject identical inputs.
        """
        payload = {
            "battery_id": request.battery_id,
            "readings": [list(r.values) for r in request.readings],
        }
        if request.HasField("pack_config"):
            payload["pack_config"] = _pack_config_dict(request.pack_config)

        validated = _validate(PredictLongRequest, payload, context)
        pack = validated.pack_config
        result = predict_soh_long(
            validated.readings,
            n_series=pack.n_series if pack else 1,
            capacity_ah=pack.capacity_ah if pack else None,
        )
        return ai_service_pb2.PredictLongResponse(
            battery_id=validated.battery_id,
            soh_percent=result["soh_percent"],
            seq_len=result["seq_len"],
            device=result["device"],
            inference_ms=result["inference_ms"],
            model_version=result["model_version"],
        )

    def SubmitClassificationFeedback(self, request, context):
        """F4 — ghi nhận kỹ thuật viên chấm lại phân loại. Mirror POST /predict/feedback."""
        validated = _validate(
            ClassificationFeedbackRequest,
            {
                "battery_id": request.battery_id,
                "classification": request.classification,
                "verdict": request.verdict,
                "model_version": request.model_version,
                "classified_at": request.classified_at,
                "note": request.note,
            },
            context,
        )
        try:
            counts = record_feedback(
                battery_id=validated.battery_id,
                classification=validated.classification,
                verdict=validated.verdict,
                model_version=validated.model_version,
                classified_at=validated.classified_at,
                note=validated.note,
            )
        except ValueError as exc:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        return ai_service_pb2.ClassificationFeedbackResponse(
            success=True,
            total=counts["total"],
            correct=counts["correct"],
            false_positive=counts["false_positive"],
            false_negative=counts["false_negative"],
            # has_* phân biệt "chưa ai chấm" với "đã chấm và sai hết" — proto3 scalar
            # không nullable nên 0.0 một mình là mơ hồ đúng ở chỗ nguy hiểm nhất.
            precision=counts["precision"] or 0.0,
            has_precision=counts["precision"] is not None,
            recall=counts["recall"] or 0.0,
            has_recall=counts["recall"] is not None,
        )

    def VerifyTicket(self, request, context):
        """Chấm điểm ticket thủ công thật/rác + dò trùng. Mirror POST /verify-ticket."""
        payload = {
            "title": request.title,
            "description": request.description,
            "detected_at": request.detected_at,
            "category": request.category,
            "sensor_snapshot": {
                "soh_percent": request.sensor_snapshot.soh_percent,
                "voltage": request.sensor_snapshot.voltage,
                "current": request.sensor_snapshot.current,
                "temperature": request.sensor_snapshot.temperature,
                "soc_percent": request.sensor_snapshot.soc_percent,
                "has_active_alert": request.sensor_snapshot.has_active_alert,
            }
            if request.has_sensor_snapshot
            else None,
            "candidates": [
                {
                    "ticket_id": c.ticket_id,
                    "description": c.description,
                    "category": c.category,
                }
                for c in request.candidates
            ],
        }
        req = _validate(VerifyTicketRequest, payload, context)
        result = run_verify(req)
        return ai_service_pb2.VerifyTicketResponse(
            verdict=result.verdict,
            score=result.score,
            reason=result.reason,
            duplicate_of_ticket_id=result.duplicate_of_ticket_id,
            duplicate_score=result.duplicate_score,
            duplicate_reason=result.duplicate_reason,
        )

    def SubmitFeedback(self, request, context):
        """Ghi phản hồi KTV cho 1 prescription. Mirror POST /prescribe/feedback."""
        req = _validate(
            PrescriptionFeedbackRequest,
            {
                "prescription_id": request.prescription_id,
                "status": request.status,
                # proto không có optional cho repeated/string: rỗng ⇒ None để khớp
                # đúng payload REST (schema cho phép None, không cho phép [] rỗng
                # mang nghĩa "đã sửa nhưng không còn bước nào").
                "edited_steps": list(request.edited_steps) or None,
                "note": request.note or None,
            },
            context,
        )
        ok = submit_prescription_feedback(
            prescription_id = req.prescription_id,
            status          = req.status,
            edited_steps    = req.edited_steps,
            note            = req.note,
        )
        if not ok:
            # REST trả 404 ở đúng nhánh này — giữ parity bằng NOT_FOUND.
            context.abort(grpc.StatusCode.NOT_FOUND, "prescription_id not found")
        return ai_service_pb2.SubmitFeedbackResponse(success=True)

    def SuggestStaff(self, request, context):
        """Xếp hạng nhân viên phù hợp xử lý ticket. Mirror POST /suggest/staff."""
        req = _validate(
            SuggestStaffRequest,
            {
                "category": request.category,
                "priority": request.priority,
                "description": request.description,
                "top_n": request.top_n,
                "candidates": [
                    {
                        "staff_id": c.staff_id,
                        "full_name": c.full_name,
                        "skill_tier": c.skill_tier,
                        "skill_codes": list(c.skill_codes),
                        "active_tickets": c.active_tickets,
                        "max_concurrent": c.max_concurrent,
                    }
                    for c in request.candidates
                ],
            },
            context,
        )
        result = run_suggest_staff(req)
        return ai_service_pb2.SuggestStaffResponse(
            suggestions=[
                ai_service_pb2.StaffSuggestion(
                    staff_id=s.staff_id,
                    full_name=s.full_name,
                    score=s.score,
                    reason=s.reason,
                    tier_ok=s.tier_ok,
                )
                for s in result.suggestions
            ],
            note=result.note,
        )

    def SuggestKb(self, request, context):
        """Xếp hạng bài viết KB để tham khảo khi sửa chữa. Mirror POST /suggest/kb."""
        req = _validate(
            SuggestKbRequest,
            {
                "category": request.category,
                "description": request.description,
                "top_n": request.top_n,
                "ai_action_steps": list(request.ai_action_steps),
                "ai_sop_references": list(request.ai_sop_references),
                "ai_kb_doc_refs": list(request.ai_kb_doc_refs),
                "candidates": [
                    {
                        "kb_id": c.kb_id,
                        "code": c.code,
                        "title": c.title,
                        "tags": list(c.tags),
                        "category": c.category,
                        "helpful_count": c.helpful_count,
                    }
                    for c in request.candidates
                ],
            },
            context,
        )
        result = run_suggest_kb(req)
        return ai_service_pb2.SuggestKbResponse(
            suggestions=[
                ai_service_pb2.KbSuggestion(
                    kb_id=s.kb_id,
                    code=s.code,
                    title=s.title,
                    score=s.score,
                    reason=s.reason,
                )
                for s in result.suggestions
            ],
            note=result.note,
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
