# Scraply - project notes for AI agents

Single product: company.info contact scraper with a web dashboard. One frontend,
one backend, one scraper engine. Read this before changing code.

## Layout (mirrors github.com/Marstark-IT/greenbaycapital)
```
frontend/   Next.js 16 (App Router, JSX, Tailwind) - STATIC EXPORT (output: "export")
  src/app/(auth)/login|register      src/app/(dashboard)/{page,files,logs,settings}
  src/components/{layout,dashboard,forms,ui}   src/hooks   src/lib   src/data
backend/    FastAPI (async SQLAlchemy, Alembic, Postgres) + Celery (Redis)
  app/main.py  app/config.py  app/health.py  app/worker.py
  app/auth/  app/core/  app/shared/  app/domains/{jobs,files,scraply,system}/
scraply/    scraper engine (Selenium) + CLI runners run_legacy.py / run_verified.py
```

## Hard rules
- **Do not touch the scraper.** `scraply/` and `backend/app/domains/scraply/`
  (`tasks.py`, `parallel_worker.py`) are frozen: the Celery task names
  `run_automation_job` / `run_scraply_tool`, the row loop, output writing and
  the company.info search logic stay as they are. Only import paths may change
  when files move. `ruff` excludes that folder on purpose.
- **Text uses "-" never an em dash.** No subtitle line under the dashboard title.
- **UI = the prototype.** `prototype/` is the design source; `frontend/src/app/globals.css`
  is its stylesheet ported 1:1. New UI reuses those classes (`.card`, `.btn`, `.tag`,
  `.rail`, `.tbl`, `.modal`...). Tailwind is for small utilities only.
- **One transport.** `frontend/src/lib/api-client.js` is the only module that calls
  `fetch`. Add endpoints to `src/lib/api.js`.
- **No `window` during render.** Persisted values (token, theme, prefs, notifications)
  are external stores read with `useSyncExternalStore` (`src/lib/store.js`).
- Backend layering: `routes -> services -> models`. Models never import routes/services.
  Every model module is imported in `alembic/env.py` and `tests/conftest.py`.
- Settings come only from `backend/app/config.py` (`get_settings()`); env var names
  are unchanged from the original project so the VPS `.env` keeps working.

## Runtime facts
- Auth: bearer JWT in localStorage (`scraply-token`), issued by `POST /api/v1/auth/login`
  (OAuth2 password form; username or email). Registration needs `ADMIN_SECRET_KEY`.
- Dashboard is shared: every signed-in user sees and controls every job.
- Job flow: create job -> upload file -> `GET /files/csv-headers/{stored}` -> user maps
  4 columns (nothing pre-filled, on purpose) -> `PATCH /jobs/{uuid}` config -> `POST /start`.
  Frontend polls `GET /jobs/{uuid}` every 2s while running; WebSocket is a bonus.
- Results are always Excel (`.xlsx`), whatever was uploaded.
- Worker count: Settings page -> `POST /system/config/workers` writes `MAX_WORKERS`
  to `.env` and restarts systemd unit `datainfo-celery`.

## VPS
`ssh nicky-server` (76.13.145.229), checkout at `/var/www/datainfo`, services
`datainfo-api` + `datainfo-celery`, nginx serves `frontend/out`. `./deploy.sh` is the
deploy; `deploy-vps.yml` runs it on push to main. Chrome + `/usr/local/bin/chromedriver`
are installed on the host. Run scrapes on the VPS, not on a laptop.

## Checks before handing over
```
cd backend && make check         # ruff + pytest (SQLite in memory)
cd frontend && npm run lint && npm run build
```
