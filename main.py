from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

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
load_dotenv(override=False)

# noqa E402 bên dưới là CỐ Ý — hai import này phải nằm SAU load_dotenv(). Đổi thứ
# tự lại thì hôm nào có module đọc os.getenv() ngay lúc import là hỏng âm thầm.
from src.core.model_loader import load_models  # noqa: E402
from src.routers import health, predict, prescribe, suggest, verify  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()
    yield


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
