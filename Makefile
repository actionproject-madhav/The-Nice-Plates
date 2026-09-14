.DEFAULT_GOAL := help
VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

help: ## Show this list
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install everything (API, worker, web)
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -r platform/requirements.txt
	cd web && npm install

api: ## Run the API on :8000 (hosts the worker in-process)
	$(VENV)/bin/uvicorn app.main:app --reload --app-dir platform --port 8000

worker: ## Run the ML worker standalone (set EMBEDDED_WORKER=false on the API)
	$(PY) audio/worker.py

web: ## Run the frontend on :5173
	cd web && npm run dev

smoke: ## End-to-end test: login -> piece -> record -> analyse -> dashboard
	$(PY) scripts/smoke_test.py

seed: ## Fill the database with a demo musician and four weeks of practice
	$(PY) scripts/seed.py

typecheck: ## Typecheck the frontend
	cd web && npm run typecheck

.PHONY: help install api worker web smoke seed typecheck
