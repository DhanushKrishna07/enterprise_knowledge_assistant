# Enterprise Knowledge Assistant — Makefile
# Run `make help` to see all available targets.

.PHONY: help setup pull-model ingest ingest-status api ui frontend frontend-dev eval test lint seed

PYTHON   := .venv\Scripts\python
UVICORN  := .venv\Scripts\uvicorn
PYTEST   := .venv\Scripts\pytest
RUFF     := .venv\Scripts\ruff
NPM      := npm

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install all dependencies
	python -m venv .venv
	.venv\Scripts\pip install --upgrade pip
	.venv\Scripts\pip install -e ".[dev]"
	cd frontend && $(NPM) install
	@echo "Setup complete. Activate with: .venv\\Scripts\\activate"

pull-model: ## Pull the default LLM model via Ollama
	ollama pull qwen3:8b
	ollama pull qwen3:4b

seed: ## Seed demo users into the database
	$(PYTHON) scripts/seed_users.py

ingest: ## Ingest all documents from data/documents
	$(PYTHON) scripts/ingest_documents.py data/documents

ingest-status: ## Show status of latest ingestion run
	$(PYTHON) -c "from scripts.ingest_documents import show_status; show_status()"

api: ## Start the FastAPI backend server
	$(UVICORN) app.api.main:app --host 0.0.0.0 --port 8000 --reload

frontend-dev: ## Start React dev server (proxies API to :8000)
	cd frontend && $(NPM) run dev

frontend: ## Build React frontend for production
	cd frontend && $(NPM) run build

ui: frontend api ## Build frontend and start API (serves UI at http://localhost:8000)

eval: ## Run the evaluation suite (smoke test set)
	$(PYTHON) -m app.evaluation.run --golden eval/golden_qa.yaml --out docs/evaluation_report.md

eval-extended: ## Run the extended evaluation suite (100+ questions)
	$(PYTHON) -m app.evaluation.run --golden eval/golden_qa_extended.yaml --out docs/evaluation_report_extended.md

test: ## Run unit and API tests
	$(PYTEST) tests/ -v --tb=short

lint: ## Lint with ruff
	$(RUFF) check app/ tests/ scripts/

export-feedback: ## Export user feedback to CSV
	$(PYTHON) scripts/export_feedback.py
