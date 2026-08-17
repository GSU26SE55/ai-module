# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.11-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3

FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY requirements-runtime.lock ./
RUN python -m pip install --upgrade \
      pip==25.3 \
      setuptools==84.0.0 \
      wheel==0.46.3 \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 \
    && python -m pip install --require-hashes -r requirements-runtime.lock \
    && python -m pip check

# The application must never download an embedding model on its first request.
ARG EMBEDDING_MODEL_ID=sentence-transformers/all-MiniLM-L6-v2
ARG EMBEDDING_MODEL_REVISION=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='${EMBEDDING_MODEL_ID}', revision='${EMBEDDING_MODEL_REVISION}', local_dir='/opt/embedding-model', allow_patterns=['*.json','*.txt','*.safetensors','1_Pooling/*'])" \
    && HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('/opt/embedding-model')"

FROM ${PYTHON_IMAGE} AS runtime

ARG BUILD_COMMIT=unknown
ARG BUILD_VERSION=dev

LABEL org.opencontainers.image.title="Solar Battery AI Module" \
      org.opencontainers.image.revision="${BUILD_COMMIT}" \
      org.opencontainers.image.version="${BUILD_VERSION}"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HOME=/opt/huggingface \
    AI_EMBEDDING_MODEL_PATH=/opt/embedding-model \
    AI_VERIFY_MODEL_MANIFEST=true

# The upstream Python image ships build tooling in its global site-packages.
# Keep its vendored metadata patched as the final image is scanned as well as
# the application venv copied from the builder.
RUN python -m pip install --no-cache-dir --upgrade \
      pip==25.3 \
      setuptools==84.0.0 \
      wheel==0.46.3

RUN groupadd --gid 10001 ai \
    && useradd --uid 10001 --gid ai --no-create-home --home-dir /nonexistent ai

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/embedding-model /opt/embedding-model
COPY --chown=0:0 main.py ./main.py
COPY --chown=0:0 src ./src
COPY --chown=0:0 models ./models
COPY --chown=0:0 knowledge ./knowledge
COPY --chown=0:0 deploy/scripts/verify-models.py deploy/scripts/smoke-test.py ./deploy/scripts/
COPY --chmod=0555 deploy/scripts/container-entrypoint.sh /usr/local/bin/ai-entrypoint

# Git checkout permissions inherit the CI agent umask. Jenkins deliberately
# uses 0027, so COPY can otherwise preserve 0750 directories and then chown
# them to root, preventing the non-root runtime UID from traversing /app.
# `a+rX` grants read/traverse only; it does not make model data executable or
# writable.
RUN chmod -R a+rX /app

# Entrypoint ghi kb/releases + history store dưới AI_DATA_DIR (compose trỏ /app/data).
# Thư mục phải tồn tại SẴN trong image và thuộc UID runtime: khi mount một named volume
# rỗng, Docker chỉ sao chép owner/mode từ thư mục đích có trong image — đích không tồn tại
# thì volume ra root:root và UID 10001 không mkdir được.
RUN mkdir -p /app/data && chown 10001:10001 /app/data

USER 10001:10001

EXPOSE 8000 50051

HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=8 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"

ENTRYPOINT ["/usr/local/bin/ai-entrypoint"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
