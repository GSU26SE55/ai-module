# AI Module — GSU26SE55 · Makefile
# Gói các lệnh hay dùng. Chạy `make` hoặc `make help` để xem danh sách.
#
# Yêu cầu: Python 3.11 (torch 2.3.1 không hỗ trợ 3.12+). Nếu chưa có: brew install python@3.11
# Lần đầu:  make setup   → tạo .venv + cài deps
# Chạy:     make grpc  (BE gọi, :50051)  ·  make serve (REST + Swagger, :8000)

PY311    ?= python3.11
VENV     := .venv
PY       := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
PYTEST   := $(VENV)/bin/pytest
RUFF     := $(VENV)/bin/ruff
PORT     ?= 8000
GRPC_PORT ?= 50051

.DEFAULT_GOAL := help

# ── Setup ────────────────────────────────────────────────────────────────
.PHONY: setup
setup: $(VENV)/.installed ## Tạo .venv (Python 3.11) + cài deps (chạy 1 lần)

$(VENV)/.installed: requirements.txt
	@test -d $(VENV) || $(PY311) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@touch $(VENV)/.installed
	@echo "✅ Môi trường sẵn sàng. Chạy: make grpc  hoặc  make serve"

.PHONY: setup-dev
setup-dev: setup ## Cài thêm deps dev (pytest, ruff, ...)
	$(PIP) install -r requirements-dev.txt
	$(PIP) install ruff

# ── Chạy service ─────────────────────────────────────────────────────────
.PHONY: serve
serve: ## REST/FastAPI (:8000) + Swagger UI /docs — fallback transport
	$(UVICORN) main:app --reload --port $(PORT)

.PHONY: grpc
grpc: ## gRPC server (:50051) — BE gọi cái này (primary transport)
	$(PY) -m src.grpc_server

.PHONY: health
health: ## Kiểm tra REST /health (service phải đang chạy)
	@curl -s http://localhost:$(PORT)/health || echo "→ service chưa chạy? make serve trước."

.PHONY: smoke
smoke: ## Smoke test gRPC (Health + Predict) — gRPC server phải đang chạy
	$(PY) scripts/smoke_grpc.py

.PHONY: demo
demo: ## Demo đủ 4 RPC gRPC (thay Swagger cho demo)
	$(PY) scripts/grpc_client_demo.py

# ── Chất lượng ───────────────────────────────────────────────────────────
.PHONY: test
test: ## Chạy pytest + coverage (Quality Gate AI ≥ 85%)
	$(PYTEST) tests/ -v --cov=src --cov-report=term

.PHONY: lint
lint: ## ruff check
	$(RUFF) check src/ scripts/ tests/

.PHONY: format
format: ## ruff format
	$(RUFF) format src/ scripts/ tests/

.PHONY: benchmark
benchmark: ## Benchmark gRPC latency (--real-weights enforce SLA <100ms)
	$(PY) scripts/benchmark_grpc.py --real-weights

# ── Artifacts / proto ────────────────────────────────────────────────────
.PHONY: proto
proto: ## Regen Python gRPC stubs từ protos/ai_service.proto
	$(PY) scripts/gen_proto.py

.PHONY: dummy
dummy: ## Sinh dummy model artifacts (dev mode, không cần data thật)
	$(PY) -X utf8 scripts/create_dummy_artifacts.py

# ── Docker (2 container: gRPC + HTTP) ────────────────────────────────────
.PHONY: docker-build
docker-build: ## Build image ai-module
	docker build -t ai-module:latest .

.PHONY: docker-grpc
docker-grpc: docker-build ## Chạy gRPC trong container (:50051)
	docker run --rm -p $(GRPC_PORT):50051 ai-module:latest python -m src.grpc_server

.PHONY: docker-http
docker-http: docker-build ## Chạy REST trong container (:8000)
	docker run --rm -p $(PORT):8000 ai-module:latest uvicorn main:app --host 0.0.0.0 --port 8000

# ── Dọn dẹp ──────────────────────────────────────────────────────────────
.PHONY: clean
clean: ## Xóa __pycache__ + coverage
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov

.PHONY: clean-venv
clean-venv: ## Xóa .venv (làm lại make setup)
	rm -rf $(VENV)

# ── Help ─────────────────────────────────────────────────────────────────
.PHONY: help
help: ## Hiện danh sách lệnh
	@echo "AI Module — GSU26SE55 · các lệnh make:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Bắt đầu:  make setup  →  make grpc  (hoặc make serve)"
