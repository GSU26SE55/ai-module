"""Runtime configuration shared by the REST and gRPC entrypoints.

Production injects environment variables through Docker Compose.  Local
development can still use ``.env`` (or ``AI_ENV_FILE``), but real environment
variables always win so a file can never override an orchestrator secret.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_environment() -> None:
    env_file = Path(os.getenv("AI_ENV_FILE", PROJECT_ROOT / ".env"))
    if env_file.is_file():
        load_dotenv(dotenv_path=env_file, override=False)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def data_path(env_name: str, default_name: str) -> Path:
    data_root = Path(os.getenv("AI_DATA_DIR", PROJECT_ROOT / "models"))
    return Path(os.getenv(env_name, data_root / default_name))


def grpc_bind_address() -> tuple[str, int]:
    host = os.getenv("GRPC_BIND_HOST", "0.0.0.0")
    port = int(os.getenv("GRPC_PORT", "50051"))
    if not 0 <= port <= 65535:
        raise ValueError("GRPC_PORT must be between 0 and 65535")
    return host, port
