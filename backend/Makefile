.DEFAULT_GOAL := help
.PHONY: help install db-upgrade db-migration run worker flower admin lint fmt test check

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Sync deps (creates .venv)
	uv sync

db-upgrade:  ## Apply migrations
	uv run alembic upgrade head

db-migration:  ## Autogenerate a migration: make db-migration MSG="..."
	uv run alembic revision --autogenerate -m "$(MSG)"

run:  ## Run the API (reload)
	uv run uvicorn app.main:app --reload --port 8000

worker:  ## Run the scraper worker (Celery)
	uv run celery -A app.worker worker --loglevel=info --concurrency=1 --pool=prefork

flower:  ## Celery monitoring UI on :5555
	uv run celery -A app.worker flower --port=5555

admin:  ## Create a user: make admin EMAIL=a@b.c USERNAME=admin PASSWORD=secret
	uv run python scripts/create_admin.py --email "$(EMAIL)" --username "$(USERNAME)" --password "$(PASSWORD)" --superuser

lint:  ## Ruff lint
	uv run ruff check .

fmt:  ## Ruff format + autofix
	uv run ruff format . && uv run ruff check . --fix

test:  ## pytest (in-memory SQLite, no services needed)
	uv run pytest -q

check: lint test  ## Run all gates
