# Scraply - Backend

FastAPI (async SQLAlchemy + Alembic, Postgres) API and a Celery worker (Redis)
that runs the company.info scraper in `<repo>/scraply`. Organised by domain.

## Quick start
```bash
cd backend
cp .env.example .env            # fill SECRET_KEY, ADMIN_SECRET_KEY, Postgres, COMPANYINFO_*
make install                    # uv sync (or: python -m venv .venv && pip install -r requirements.txt)
make db-upgrade                 # alembic upgrade head
make run                        # API on :8000  (docs at /docs)
make worker                     # Celery scraper worker (needs Chrome + chromedriver)
make admin EMAIL=a@b.c USERNAME=admin PASSWORD=secret
```
Local Postgres + Redis: `docker compose up -d db redis` from the repo root.

## Project layout
```text
backend/
  app/
    main.py              FastAPI app factory + lifespan
    config.py            cached get_settings() - the ONLY place env is read
    health.py            /healthz, /readyz, /health (unauthenticated)
    worker.py            Celery entrypoint: celery -A app.worker worker
    core/                db (engine/session/Base), task_queue (Celery app),
                         events (WebSocket fan-out), logging, environment (URL detection)
    auth/                jwt.py, dependencies.py (get_current_user), models, schemas, routes
    shared/              canonical enums + cross-domain DTOs
    domains/
      jobs/              Job/JobLog models, routes (create/start/pause/resume/cancel/retry/
                         logs/download), services (queueing + Celery control), websocket.py
      files/             upload, list, download, delete, csv-headers (column mapping step)
      scraply/           tasks.py (run_automation_job / run_scraply_tool) + parallel_worker.py
                         = the scraper task, unchanged apart from import paths
      system/            health, stats, worker inventory, MAX_WORKERS config
  alembic/               migrations (env.py imports every model)
  scripts/               create_admin.py, start_celery.sh (systemd ExecStart on the VPS)
  tests/                 pytest on in-memory SQLite (no services needed)
  Dockerfile             API image     Dockerfile.worker   worker image (+ Chrome)
  Makefile  pyproject.toml  requirements.txt  .env.example
```

**Layering rule:** `routes -> services -> models`; models never import services or
routes; `app/` must be importable by `alembic/env.py` with no side effects.

## API
All routes live under `/api/v1`. Auth is a bearer JWT from `POST /auth/login`
(OAuth2 password form; `username` accepts username or email). Registration
(`POST /auth/register`) needs `ADMIN_SECRET_KEY`. Live progress: `WS /api/v1/ws?token=`.

## The scraper
`app/domains/scraply/tasks.py` puts `<repo>` and `<repo>/scraply` on `sys.path`
and imports the engine from `src.modules`. Do not edit the engine from here; it
has its own CLI runners (`scraply/run_legacy.py`, `scraply/run_verified.py`).

## Make targets
| `make` | Purpose |
|---|---|
| `install` | `uv sync` |
| `db-upgrade` / `db-migration MSG=...` | Alembic |
| `run` / `worker` / `flower` | API / scraper worker / Celery UI |
| `admin` | create a user without the admin key |
| `lint` / `fmt` / `test` / `check` | ruff / ruff format / pytest / all |
