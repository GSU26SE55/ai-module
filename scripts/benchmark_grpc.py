"""
GH-42 — gRPC latency benchmark: Predict unary / PredictStream / Prescribe
+ transport overhead vs direct run_inference.

Usage:
    python scripts/benchmark_grpc.py                  # dummy weights (default)
    python scripts/benchmark_grpc.py --real-weights   # production artifacts
    python scripts/benchmark_grpc.py -n 100           # more iterations

Thresholds:
    - Transport overhead < 50ms: ALWAYS enforced (the part gRPC adds).
    - Absolute Predict < 100ms (P1 SLA): enforced ONLY with --real-weights —
      dummy mode runs on dev machines where the MC-Dropout pipeline itself is
      CPU-borderline (see logs/GH-40/test.md); precedent: GH-10 enforces the
      SLA on the deploy environment.

Re-run with --real-weights once the v1.3/v2.2 artifacts land (retrain #25).
"""

import argparse
import os
import statistics
import sys
import time
from concurrent import futures

import grpc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import model_loader  # noqa: E402
from src.core.config import (
    BASE_FEATURES,
    INPUT_FEATURES,
    SPECTRAL_FEAT_DIM,
    WINDOW_SIZE,
)  # noqa: E402
from src.grpc_gen import ai_service_pb2 as pb  # noqa: E402
from src.grpc_gen import ai_service_pb2_grpc as pb_grpc  # noqa: E402
from src.grpc_server import AiServiceServicer  # noqa: E402
from src.services.inference import run_inference  # noqa: E402

SEED = 42
np.random.seed(SEED)

OVERHEAD_BUDGET_MS = 50.0
ABSOLUTE_BUDGET_MS = 100.0  # P1 SLA — enforced with --real-weights only


def install_dummy_models() -> None:
    """Small random artifacts — same pattern as tests/test_routers.py."""
    import torch
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import MinMaxScaler, StandardScaler

    from src.models.soh_predictor import MambaSOHPredictor

    torch.manual_seed(SEED)
    scaler = MinMaxScaler().fit(
        np.random.rand(50, len(BASE_FEATURES))
    )  # GH-54: 4 base cols
    feat_scaler = StandardScaler().fit(np.random.rand(50, SPECTRAL_FEAT_DIM))
    model = MambaSOHPredictor(
        input_features=INPUT_FEATURES, feat_dim=SPECTRAL_FEAT_DIM, d_model=8, d_state=4
    )
    model.eval()
    iso = IsolationForest(n_estimators=10, random_state=SEED)
    iso.fit(np.random.rand(50, SPECTRAL_FEAT_DIM))

    model_loader.scaler = scaler
    model_loader.feature_scaler = feat_scaler
    model_loader.soh_model = model
    model_loader.iso_model = iso


def stats_ms(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "avg": statistics.mean(samples),
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
    }


def timed(fn, n: int) -> dict:
    fn()  # warm-up
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return stats_ms(samples)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real-weights",
        action="store_true",
        help="load production artifacts via load_models() and enforce the <100ms SLA",
    )
    parser.add_argument(
        "-n", type=int, default=50, help="iterations per RPC (default 50)"
    )
    args = parser.parse_args()

    if args.real_weights:
        model_loader.load_models()  # raises with a clear message if artifacts are missing
        mode = "REAL weights"
    else:
        install_dummy_models()
        mode = (
            "DUMMY weights (transport-focused; re-run --real-weights after retrain #25)"
        )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_AiServiceServicer_to_server(AiServiceServicer(), server)
    port = server.add_insecure_port("localhost:0")
    server.start()
    stub = pb_grpc.AiServiceStub(grpc.insecure_channel(f"localhost:{port}"))

    # GH-66: readings must be physically realistic — the input range guard rejects
    # rand()∈[0,1) rows (voltage < 2.0V floor). Same shape/latency, valid values.
    rows = np.random.rand(WINDOW_SIZE, len(BASE_FEATURES))
    rows[:, 0] = 3.5 + rows[:, 0] * 0.6  # voltage [3.5, 4.1] V
    rows[:, 1] = -2.0 + rows[:, 1] * 4.0  # current [-2, 2] A
    rows[:, 2] = 20.0 + rows[:, 2] * 10.0  # temperature [20, 30] °C
    rows[:, 3] = np.arange(WINDOW_SIZE) * 10.0  # time (s, cumulative)
    readings_lists = rows.tolist()
    readings_proto = [pb.Reading(values=row) for row in readings_lists]
    predict_req = pb.PredictRequest(battery_id="B0005", readings=readings_proto)
    prescribe_req = pb.PrescribeRequest(
        battery_id="B0005", readings=readings_proto, enrich=False
    )

    print(f"gRPC benchmark — {mode} | n={args.n} per RPC\n")

    direct = timed(lambda: run_inference(readings_lists), args.n)
    predict = timed(lambda: stub.Predict(predict_req), args.n)
    prescribe = timed(lambda: stub.Prescribe(prescribe_req), args.n)

    # Stream: n windows through one call; per-window figures
    stream_batch = 10

    def stream_once():
        assert (
            sum(1 for _ in stub.PredictStream(iter([predict_req] * stream_batch)))
            == stream_batch
        )

    stream_total = timed(stream_once, max(5, args.n // stream_batch))
    stream = {k: v / stream_batch for k, v in stream_total.items()}

    overhead = predict["avg"] - direct["avg"]

    header = f"{'RPC':<28}{'avg ms':>10}{'p50 ms':>10}{'p95 ms':>10}"
    print(header)
    print("-" * len(header))
    for name, s in (
        ("run_inference (direct)", direct),
        ("Predict (unary)", predict),
        ("PredictStream (per window)", stream),
        ("Prescribe (rule path)", prescribe),
    ):
        print(f"{name:<28}{s['avg']:>10.1f}{s['p50']:>10.1f}{s['p95']:>10.1f}")
    print(f"\nTransport overhead (Predict avg - direct avg): {overhead:.1f}ms")

    server.stop(grace=None)

    failed = False
    if overhead >= OVERHEAD_BUDGET_MS:
        print(f"FAIL: transport overhead {overhead:.1f}ms >= {OVERHEAD_BUDGET_MS}ms")
        failed = True
    if args.real_weights and predict["avg"] >= ABSOLUTE_BUDGET_MS:
        print(
            f"FAIL: Predict avg {predict['avg']:.1f}ms >= {ABSOLUTE_BUDGET_MS}ms (P1 SLA)"
        )
        failed = True

    print(
        "\nRESULT:",
        "FAIL" if failed else "PASS",
        "" if args.real_weights else "(absolute <100ms SLA not enforced in dummy mode)",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
