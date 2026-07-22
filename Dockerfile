# AI Module — GSU26SE55
# Serves the same inference/prescription pipeline over two transports (hybrid):
#   - gRPC  : python -m src.grpc_server   (port 50051, BE primary)
#   - REST  : uvicorn main:app            (port 8000, BE fallback + Swagger)
# The transport is chosen by the container command (docker-compose), not baked in —
# one image, two services. See docs/grpc-integration-be.md.

FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal — pure-PyTorch model needs no CUDA/BLAS extras beyond wheels.
RUN pip install --no-cache-dir --upgrade pip

# Install deps first (layer cache) — requirements pin exact versions.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + committed model artifacts (models/weights/*.pth,*.pkl are in the repo).
COPY . .

# Default = REST. docker-compose overrides `command:` for the gRPC service.
EXPOSE 8000 50051
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
