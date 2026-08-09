from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.model_loader import load_models
from src.routers import health, predict, prescribe, suggest, verify


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
