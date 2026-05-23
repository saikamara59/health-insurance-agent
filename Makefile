.PHONY: help install test lint clean seed data dev frontend build docker docker-up docker-down check all

# Default
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────────────

install: ## Install all dependencies (backend + frontend)
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

install-backend: ## Install backend dependencies only
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

install-frontend: ## Install frontend dependencies only
	cd frontend && npm install

# ─── Data ─────────────────────────────────────────────────────────────────────

seed: ## Seed demo broker + sample clients (requires running server)
	.venv/bin/python seed.py

data: ## Load real CMS/FDA health data (seed mode)
	.venv/bin/python scripts/refresh_data.py --seed-only

data-full: ## Download full CMS/FDA data from public APIs
	.venv/bin/python scripts/refresh_data.py

# ─── Testing ──────────────────────────────────────────────────────────────────

test: ## Run all backend tests
	.venv/bin/python -m pytest healthflow/tests/ -v --tb=short

test-quick: ## Run tests without verbose output
	.venv/bin/python -m pytest healthflow/tests/ -q --tb=short

test-cov: ## Run tests with coverage report
	.venv/bin/pip install coverage -q
	.venv/bin/python -m coverage run -m pytest healthflow/tests/ -q --tb=short
	.venv/bin/python -m coverage report --include="healthflow/**" --omit="healthflow/tests/**"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	.venv/bin/pip install pytest-watch -q
	.venv/bin/ptw healthflow/tests/

smoke-external: ## Run opt-in live smoke tests against RxNav + NPPES (needs internet)
	LIVE_SMOKE_TESTS=1 .venv/bin/python -m pytest healthflow/tests/integration/ -v

# ─── Linting ──────────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	.venv/bin/pip install ruff -q
	.venv/bin/ruff check healthflow/ --select F,E,W --ignore E501

lint-fix: ## Auto-fix lint issues
	.venv/bin/pip install ruff -q
	.venv/bin/ruff check healthflow/ --select F401 --fix

dead-code: ## Find dead code with vulture
	# --ignore-names silences framework-callback params that ARE required by the API
	# but never used in the body: `cls`/`__context` (Pydantic validators),
	# `dialect` (SQLAlchemy TypeDecorator), `multiparams`/`execution_options`/`flush_context`
	# (SQLAlchemy event listener signatures). Removing them breaks the framework integration.
	.venv/bin/pip install vulture -q
	.venv/bin/vulture healthflow/ --min-confidence 90 \
		--ignore-names "cls,__context,dialect,multiparams,execution_options,flush_context"

# ─── Development ──────────────────────────────────────────────────────────────

dev: ## Start backend dev server
	.venv/bin/python -m healthflow.main

frontend: ## Start frontend dev server
	cd frontend && npm run dev

build: ## Build frontend for production
	cd frontend && npm run build

# ─── Docker ───────────────────────────────────────────────────────────────────

docker: ## Build all Docker images
	docker compose build

docker-up: ## Start all services (backend + frontend + redis)
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Show logs from all services
	docker compose logs -f

docker-reset: ## Stop, remove volumes, rebuild
	docker compose down -v
	docker compose build --no-cache
	docker compose up -d

# ─── Full Checks ──────────────────────────────────────────────────────────────

check: lint test build ## Run lint + tests + frontend build
	@echo "\n\033[32m✓ All checks passed\033[0m"

all: install data check ## Full setup: install, load data, run checks
	@echo "\n\033[32m✓ HealthFlow is ready\033[0m"

clean: ## Remove generated files
	rm -rf .venv/ frontend/node_modules/ frontend/dist/ healthflow_data.db healthflow.db healthflow.log __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
