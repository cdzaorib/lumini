UV ?= $(if $(wildcard .tools/bin/uv),$(abspath .tools/bin/uv),uv)

.PHONY: install backend-check backend-integration frontend-check secrets-check check api web e2e

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

# gitleaks 8.30.1 (checksum in .github/workflows/checks.yml) in PATH or .tools/bin.
GITLEAKS ?= $(if $(wildcard .tools/bin/gitleaks),$(abspath .tools/bin/gitleaks),gitleaks)

secrets-check:
	$(GITLEAKS) git --redact --no-banner .

check: secrets-check backend-check frontend-check

api:
	cd backend && $(UV) run --frozen uvicorn lumini.app:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-access-log

web:
	cd frontend && npm run dev

# Browser scenarios with synthetic data; needs LUMINI_E2E_* local test services, Chrome, Node 22.
e2e:
	cd e2e && npm ci && node run.mjs
