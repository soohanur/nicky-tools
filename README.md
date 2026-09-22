# Scraply

Contact extraction from company.info. Upload a CSV or Excel file of companies,
map four columns, press Start; Scraply scrapes phone numbers and emails in
headless Chrome and hands back an enriched Excel file. Login and registration
(admin-key gated) go straight to the dashboard.

Live: https://nicky.tools

## Layout
```
scraply/
  frontend/     Next.js 16 dashboard, static export served by nginx   -> frontend/README.md
  backend/      FastAPI API + Celery worker, organised by domain      -> backend/README.md
  scraply/      the scraper engine (Selenium) + CLI runners. Do not restructure.
  docs/         runbooks, architecture notes, older deployment guides
  prototype/    the HTML/CSS prototype the UI is built from
  deploy.sh     VPS deploy (systemd + nginx)      docker-compose.yml   local full stack
  .github/workflows/deploy-vps.yml   push to main -> ./deploy.sh on the VPS
```

## Run locally
```bash
docker compose up -d db redis                 # Postgres + Redis
cd backend && cp .env.example .env && make install && make db-upgrade && make run
cd backend && make worker                     # scraper worker (needs Chrome + chromedriver)
cd frontend && cp .env.example .env.local && npm install && npm run dev   # http://localhost:3000
```
Or the whole stack in containers: `cp .env.example .env && docker compose up --build`.

## Deploy
The VPS runs `datainfo-api` (uvicorn) and `datainfo-celery` (Celery, prefork,
one Chrome per worker process) under systemd; nginx serves `frontend/out` and
proxies `/api/` to the API. `./deploy.sh` does the whole thing; `./deploy.sh --quick`
just restarts the services after a code pull.

## Checks
```bash
cd backend && make check          # ruff + pytest (SQLite in memory, no services)
cd frontend && npm run lint && npm run build
```
