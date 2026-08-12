#!/usr/bin/env python3
"""Production smoke: REST/gRPC readiness plus real NASA and LFP inference."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from src.grpc_gen import ai_service_pb2 as pb
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return json.load(response)


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"{url} returned HTTP {response.status}")
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body}") from exc


def main() -> int:
    rest_base = os.getenv("AI_SMOKE_REST_URL", "http://127.0.0.1:8000")
    grpc_target = os.getenv("AI_SMOKE_GRPC_TARGET", "127.0.0.1:50051")
    grpc_tls = os.getenv("AI_SMOKE_GRPC_TLS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    grpc_authority = os.getenv("AI_SMOKE_GRPC_AUTHORITY", "").strip()

    live = fetch_json(f"{rest_base}/live")
    ready = fetch_json(f"{rest_base}/ready")
    if live.get("status") != "live" or ready.get("status") != "ready":
        raise RuntimeError(f"AI is not ready: live={live}, ready={ready}")

    rest_payload = {
        "battery_id": "production-smoke-rest",
        "readings": [
            [3.9 - index * 0.01, -1.0, 25.0 + index * 0.1, float(index * 13)]
            for index in range(30)
        ],
    }
    rest_prediction = post_json(f"{rest_base}/predict/", rest_payload)
    if not 0.0 <= rest_prediction.get("soh_percent", -1.0) <= 100.0:
        raise RuntimeError(f"Invalid REST prediction: {rest_prediction}")

    if grpc_tls:
        channel_options = []
        if grpc_authority:
            channel_options.extend(
                [
                    ("grpc.default_authority", grpc_authority),
                    ("grpc.ssl_target_name_override", grpc_authority),
                ]
            )
        channel = grpc.secure_channel(
            grpc_target,
            grpc.ssl_channel_credentials(),
            options=channel_options,
        )
    else:
        channel = grpc.insecure_channel(grpc_target)
    grpc.channel_ready_future(channel).result(timeout=15)
    standard = health_pb2_grpc.HealthStub(channel).Check(
        health_pb2.HealthCheckRequest(service="aimodule.v1.AiService"), timeout=10
    )
    if standard.status != health_pb2.HealthCheckResponse.SERVING:
        raise RuntimeError(f"Standard gRPC health is not SERVING: {standard.status}")

    client = pb_grpc.AiServiceStub(channel)
    custom = client.Health(pb.HealthRequest(), timeout=10)
    if not (
        custom.scaler_loaded
        and custom.mamba_loaded
        and custom.isolation_forest_loaded
        and custom.lfp_loaded
    ):
        raise RuntimeError(f"Required model set is incomplete: {custom}")

    request = pb.PredictRequest(battery_id="production-smoke")
    for index in range(30):
        request.readings.add(
            values=[3.9 - index * 0.01, -1.0, 25.0 + index * 0.1, float(index * 13)]
        )
    nasa_prediction = client.Predict(request, timeout=30)
    if not 0.0 <= nasa_prediction.soh_percent <= 100.0:
        raise RuntimeError(
            f"Invalid NASA SOH from production smoke: {nasa_prediction.soh_percent}"
        )

    lfp_request = pb.PredictRequest(battery_id="production-smoke-lfp")
    lfp_request.pack_config.n_series = 1
    lfp_request.pack_config.chemistry = "LFP"
    lfp_request.pack_config.capacity_ah = 1.1
    for index in range(30):
        lfp_request.reading_objects.add(
            voltage=3.45 - index * 0.01,
            current=-1.0,
            temperature=30.0 + index * 0.05,
            time=float(index * 30),
            cycle_count=100.0,
            soc_percent=95.0 - index * 2.5,
        )
    lfp_prediction = client.Predict(lfp_request, timeout=30)
    if not 0.0 <= lfp_prediction.soh_percent <= 100.0:
        raise RuntimeError(
            f"Invalid LFP SOH from production smoke: {lfp_prediction.soh_percent}"
        )
    if lfp_prediction.metadata.chemistry != "LFP":
        raise RuntimeError(
            "LFP smoke did not select the LFP artifact path: "
            f"{lfp_prediction.metadata}"
        )

    channel.close()
    print(
        json.dumps(
            {
                "status": "ok",
                "model_version": custom.model_version,
                "lfp_model_version": custom.lfp_model_version,
                "rest_soh_percent": rest_prediction["soh_percent"],
                "nasa_soh_percent": nasa_prediction.soh_percent,
                "nasa_classification": nasa_prediction.classification,
                "nasa_inference_ms": nasa_prediction.inference_ms,
                "lfp_soh_percent": lfp_prediction.soh_percent,
                "lfp_classification": lfp_prediction.classification,
                "lfp_inference_ms": lfp_prediction.inference_ms,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AI production smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
