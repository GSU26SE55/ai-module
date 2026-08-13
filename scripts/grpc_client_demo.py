
"""
GH-42 — gRPC client demo: gọi đủ 4 RPC của AiService (thay Swagger khi demo).

Yêu cầu server đang chạy:  python -m src.grpc_server   (cần artifacts thật)

Usage:
    python scripts/grpc_client_demo.py
    GRPC_HOST=ai-module GRPC_PORT=50051 python scripts/grpc_client_demo.py

BE tham khảo file này để hiểu cách gọi từng RPC — C# tương đương xem
docs/grpc-integration-be.md.
"""

import os
import sys

import grpc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import BASE_FEATURES, WINDOW_SIZE  # noqa: E402
from src.grpc_gen import ai_service_pb2 as pb  # noqa: E402
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc  # noqa: E402

SEED = 42
np.random.seed(SEED)

# Console Windows mặc định cp1252 — không in được tiếng Việt
sys.stdout.reconfigure(encoding="utf-8")

HOST = os.getenv("GRPC_HOST", "localhost")
PORT = int(os.getenv("GRPC_PORT", 50051))
CONNECT_TIMEOUT_S = 5


def make_window(battery_id: str) -> pb.PredictRequest:
    """One synthetic 30-timestep window (4 features: V, I, T, time)."""
    rows = np.random.rand(WINDOW_SIZE, len(BASE_FEATURES))
    rows[:, 0] = 3.5 + rows[:, 0] * 0.7  # voltage ~ [3.5, 4.2] V
    rows[:, 1] = 1.0 + rows[:, 1]  # current ~ [1, 2] A
    rows[:, 2] = 24.0 + rows[:, 2] * 6  # temperature ~ [24, 30] °C
    rows[:, 3] = np.arange(WINDOW_SIZE) * 10.0  # time (s, cumulative)
    return pb.PredictRequest(
        battery_id=battery_id,
        readings=[pb.Reading(values=row.tolist()) for row in rows],
    )


def main() -> int:
    channel = grpc.insecure_channel(f"{HOST}:{PORT}")
    try:
        grpc.channel_ready_future(channel).result(timeout=CONNECT_TIMEOUT_S)
    except grpc.FutureTimeoutError:
        print(f"Không kết nối được gRPC server tại {HOST}:{PORT}.")
        print("Khởi động server trước:  python -m src.grpc_server")
        print("(cần artifacts trong models/weights/ — xem docs/grpc-integration-be.md)")
        return 1

    stub = pb_grpc.AiServiceStub(channel)

    print(f"=== AiService demo @ {HOST}:{PORT} ===\n")

    # 1. Health
    health = stub.Health(pb.HealthRequest())
    print(
        f"[1] Health: status={health.status} | model v{health.model_version} | "
        f"scaler={health.scaler_loaded} mamba={health.mamba_loaded} "
        f"iso_forest={health.isolation_forest_loaded}\n"
    )

    # 2. Predict (unary) — 1 window 30×4
    predict = stub.Predict(make_window("B0005"))
    print(
        f"[2] Predict B0005: SOH={predict.soh_percent:.1f}% "
        f"({predict.classification}, confidence={predict.confidence:.2f}) | "
        f"RUL~{predict.rul_cycles_estimate} cycles | "
        f"action={predict.recommended_action} | {predict.inference_ms:.0f}ms\n"
    )

    # 3. PredictStream (bidi) — 3 windows trên 1 connection, response đúng thứ tự
    windows = [make_window(f"B000{i}") for i in range(5, 8)]
    print("[3] PredictStream (3 windows):")
    for response in stub.PredictStream(iter(windows)):
        print(
            f"      {response.battery_id}: SOH={response.soh_percent:.1f}% "
            f"({response.classification})"
        )
    print()

    # 4. Prescribe (rule-based, enrich=False — hot path <100ms)
    window = make_window("B0005")
    prescribe = stub.Prescribe(
        pb.PrescribeRequest(
            battery_id=window.battery_id, readings=window.readings, enrich=False
        )
    )
    print(
        f"[4] Prescribe B0005: risk={prescribe.risk_level} priority={prescribe.priority}"
    )
    print(f"      prescription: {prescribe.prescription}")
    for step in prescribe.action_steps:
        print(f"      - {step}")
    print(f"      human_verification_required={prescribe.human_verification_required}")

    print("\n=== demo hoàn tất ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
