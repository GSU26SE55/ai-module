import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from prometheus_client import make_asgi_app

from src.core.runtime import env_bool, grpc_bind_address, load_environment

# Nạp .env NGAY khi import, trước mọi os.getenv() phía dưới.
#
# Trước đây không chỗ nào gọi hàm này và không lệnh chạy nào truyền `--env-file`,
# nên DEEPSEEK_API_KEY trong .env chưa bao giờ tới được process: chain.is_available()
# luôn False → mọi request enrich=true âm thầm rơi về rule-based, và cả tầng RAG/SOP
# (13 file knowledge, 64 chunk) chưa từng chạy một lần nào. Không có lỗi nào được
# raise — response vẫn 200, chỉ khác `llm_provider: "none"`.
#
# override=False là CỐ Ý: biến môi trường thật (docker `env_file`, secrets của
# orchestrator) phải thắng file .env trên đĩa.
load_environment()

# noqa E402 bên dưới là CỐ Ý — hai import này phải nằm SAU load_dotenv(). Đổi thứ
# tự lại thì hôm nào có module đọc os.getenv() ngay lúc import là hỏng âm thầm.
from src.core.artifact_manifest import verify_model_manifest  # noqa: E402
from src.core.metrics import HTTP_DURATION, HTTP_REQUESTS  # noqa: E402
from src.core.model_loader import load_models  # noqa: E402
from src.grpc_server import create_server, mark_server_not_serving  # noqa: E402
from src.routers import health, predict, prescribe, suggest, verify  # noqa: E402
from src.services.prescription.orchestrator import (  # noqa: E402
    prescription_dependencies_ready,
    prewarm_prescription_dependencies,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_model_manifest()
    load_models()

    if env_bool("AI_PRELOAD_RAG", default=False):
        prewarm_prescription_dependencies()
        if env_bool("AI_REQUIRE_RAG", default=False) and not prescription_dependencies_ready():
            raise RuntimeError("RAG dependencies failed production startup readiness")

    grpc_server = None
    if env_bool("AI_ENABLE_GRPC", default=False):
        host, port = grpc_bind_address()
        grpc_server = create_server(port=port, host=host)
        grpc_server.start()
        logger.info("gRPC server started on %s:%d", host, port)

    app.state.grpc_server = grpc_server
    try:
        yield
    finally:
        if grpc_server is not None:
            mark_server_not_serving(grpc_server)
            grpc_server.stop(grace=10).wait()
            logger.info("gRPC server stopped")


app = FastAPI(
    title="AI Module — Solar Battery Maintenance",
    description="SOH prediction and anomaly detection for lithium-ion batteries.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(predict.router)
app.include_router(prescribe.router)
app.include_router(verify.router)
app.include_router(suggest.router)


@app.middleware("http")
async def prometheus_http_metrics(request: Request, call_next):
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        status = str(response.status_code if response is not None else 500)
        HTTP_REQUESTS.labels(request.method, path, status).inc()
        HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - started)


app.mount("/metrics", make_asgi_app())
