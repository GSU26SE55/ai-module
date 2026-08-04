"""Smoke test gRPC — gọi Health + Predict, xác nhận server connect được.

Chạy: python scripts/smoke_grpc.py   (sau khi `python -m src.grpc_server` đang chạy)
"""
import grpc

from src.grpc_gen import ai_service_pb2 as pb
from src.grpc_gen import ai_service_pb2_grpc as pbg

ch = grpc.insecure_channel("localhost:50051")
grpc.channel_ready_future(ch).result(timeout=30)  # đợi server sẵn sàng
cli = pbg.AiServiceStub(ch)

h = cli.Health(pb.HealthRequest())
print(
    "HEALTH:", h.status, "| model", h.model_version,
    "| scaler", h.scaler_loaded, "| mamba", h.mamba_loaded,
    "| iso", h.isolation_forest_loaded,
)

# Predict — 30 timestep × 4 features [voltage, current, temperature, time]
req = pb.PredictRequest(battery_id="B0005")
for t in range(30):
    r = pb.Reading()
    r.values.extend([3.9 - t * 0.01, -1.0, 25.0 + t * 0.1, float(t * 13)])
    req.readings.append(r)
resp = cli.Predict(req)
print(
    "PREDICT: soh=%.2f%% | class=%s | conf=%.2f | priority=%s | action=%s | ms=%.1f"
    % (
        resp.soh_percent, resp.classification, resp.confidence,
        resp.risk.priority, resp.recommended_action, resp.inference_ms,
    )
)
print("SMOKE_OK ✅ — gRPC connect thành công")
