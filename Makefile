UV ?= $(if $(wildcard .tools/bin/uv),$(abspath .tools/bin/uv),uv)

.PHONY: install backend-check backend-integration frontend-check check api web

install:
	$(UV) sync --project backend --frozen
	cd frontend && npm ci

backend-check:
	cd backend && $(UV) run --frozen ruff check .
	cd backend && $(UV) run --frozen ruff format --check .
	cd backend && $(UV) run --frozen mypy
	cd backend && $(UV) run --frozen pytest

# Requires explicit LUMINI_INTEGRATION_* URLs pointing to isolated test services.
backend-integration:
	cd backend && $(UV) run --frozen pytest -m integration

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run build

check: backend-check frontend-check

api:
	cd backend && $(UV) run --frozen uvicorn lumini.app:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-access-log

web:
	cd frontend && npm run dev
