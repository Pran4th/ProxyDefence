.PHONY: help setup infra-start infra-stop infra-restart start stop status \
        test test-unit test-integration test-cov lint format typecheck \
        pipeline-test seed-demo reset-db clean

# ─── Detect OS ────────────────────────────────────────────────────────────
UNAME := $(shell uname -s)
ifeq ($(UNAME), Linux)
    POWERSHELL := pwsh
else ifeq ($(UNAME), Darwin)
    POWERSHELL := pwsh
else
    POWERSHELL := pwsh
endif

# ─── Help ─────────────────────────────────────────────────────────────────

help: ## List all available targets
	@echo "ProxyDefence — Makefile"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ────────────────────────────────────────────────────────────────

setup: ## Run setup.ps1 (create venvs, install deps, download spaCy model)
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/setup/setup.ps1

# ─── Infrastructure ───────────────────────────────────────────────────────

infra-start: ## Start Docker infrastructure (PostgreSQL, Kafka, Elasticsearch)
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/infrastructure/start-infra.ps1

infra-stop: ## Stop Docker infrastructure
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/infrastructure/stop-infra.ps1

infra-restart: ## Restart Docker infrastructure
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/infrastructure/restart-infra.ps1

# ─── Service Management ───────────────────────────────────────────────────

start: ## Start all services (infra + backend + frontend + consumers)
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/start-local.ps1

stop: ## Stop all services
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/stop-local.ps1

status: ## Check status of all services
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/status.ps1

# ─── Testing ──────────────────────────────────────────────────────────────

test: ## Run all tests
	python -m pytest tests/ -v --timeout=30

test-unit: ## Run unit tests only
	python -m pytest tests/unit -v

test-integration: ## Run integration tests (requires PG + ES running)
	python -m pytest tests/integration --run-integration -v

test-cov: ## Run tests with coverage report
	python -m pytest tests/ -v --timeout=30 \
		--cov=backend \
		--cov-report=term-missing \
		--cov-report=html:coverage_html

# ─── Linting & Formatting ─────────────────────────────────────────────────

lint: ## Run ruff linter
	ruff check backend/ services/ --config pyproject.toml

format: ## Run ruff formatter
	ruff format backend/ services/ --config pyproject.toml

format-check: ## Check formatting without changes
	ruff format --check backend/ services/ --config pyproject.toml

typecheck: ## Run pyright type checker
	python -m pyright backend/ services/

# ─── Pipeline & Data ──────────────────────────────────────────────────────

pipeline-test: ## Run pipeline integration test
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/test/pipeline-test.ps1

seed-demo: ## Seed demo data (requires energy-service running with ENERGY_LOAD_SEED=1)
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/test/seed-demo-data.ps1

reset-db: ## Reset database (drop + recreate schemas)
	$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/dev/test/reset-db.ps1

# ─── Cleanup ──────────────────────────────────────────────────────────────

clean: ## Clean __pycache__, logs, .ruff_cache, .pytest_cache, coverage
	@echo "Cleaning project artifacts..."
	-find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	-find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	-find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	-find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	-find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	-rm -rf logs/ coverage_html/ .coverage 2>/dev/null || true
	@echo "Clean complete."

distclean: ## Clean everything including venvs and node_modules
	$(MAKE) clean
	@echo "Removing virtual environments..."
	-find services -type d -name ".venv" -exec rm -rf {} + 2>/dev/null || true
	@echo "Removing node_modules..."
	-rm -rf services/frontend/node_modules 2>/dev/null || true
	@echo "Distclean complete."
