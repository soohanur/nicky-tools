#!/bin/bash
# Deploy Scraply on the VPS (systemd + nginx, no Docker).
# Run from the checkout root on the server, e.g. /var/www/datainfo. Idempotent.
#
#   ./deploy.sh              # full: deps, migrations, frontend build, services, nginx
#   ./deploy.sh --quick      # code already pulled: restart API + worker only
#
# Expects backend/.env (see backend/.env.example). Service names stay
# datainfo-api / datainfo-celery so existing monitoring keeps working.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_SERVICE=datainfo-api
WORKER_SERVICE=datainfo-celery
SITE_NAME=scraply
RUN_USER="${RUN_USER:-$USER}"
DOMAIN="${DOMAIN_NAME:-}"

info() { echo -e "\033[0;34m>\033[0m $1"; }
ok() { echo -e "\033[0;32mok\033[0m $1"; }

cd "$PROJECT_DIR"

if [ "${1:-}" = "--quick" ]; then
    sudo systemctl restart "$API_SERVICE" "$WORKER_SERVICE"
    sleep 5
    systemctl is-active "$API_SERVICE" "$WORKER_SERVICE"
    exit 0
fi

[ -f backend/.env ] || { echo "backend/.env missing (copy backend/.env.example)"; exit 1; }
# shellcheck disable=SC1091
set -a; source backend/.env; set +a
DOMAIN="${DOMAIN:-${DOMAIN_NAME:-}}"
[ -n "$DOMAIN" ] || { echo "DOMAIN_NAME not set in backend/.env"; exit 1; }

info "backend dependencies"
cd backend
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt
ok "python deps"

info "database migrations"
./venv/bin/alembic upgrade head
ok "alembic"
cd "$PROJECT_DIR"

info "directories"
mkdir -p logs chrome_profiles scraply/csv_files/input scraply/csv_files/output
ok "directories"

info "frontend build (static export)"
cd frontend
# Same origin in production: nginx proxies /api/ to the API, so the URL stays empty.
NEXT_PUBLIC_API_URL="" npm ci --no-audit --no-fund
NEXT_PUBLIC_API_URL="" npm run build
ok "frontend/out"
cd "$PROJECT_DIR"

info "systemd units"
sudo tee /etc/systemd/system/$API_SERVICE.service > /dev/null <<EOF
[Unit]
Description=Scraply API (FastAPI)
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin"
Environment="PYTHONPATH=$PROJECT_DIR/backend:$PROJECT_DIR/scraply"
EnvironmentFile=$PROJECT_DIR/backend/.env
ExecStart=$PROJECT_DIR/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/$WORKER_SERVICE.service > /dev/null <<EOF
[Unit]
Description=Scraply scraper worker (Celery)
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_USER
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONPATH=$PROJECT_DIR/backend:$PROJECT_DIR/scraply"
EnvironmentFile=$PROJECT_DIR/backend/.env
ExecStart=/bin/bash $PROJECT_DIR/backend/scripts/start_celery.sh
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
chmod +x backend/scripts/start_celery.sh
ok "units written"

info "nginx"
sudo tee /etc/nginx/sites-available/$SITE_NAME > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 100M;
    proxy_connect_timeout 600;
    proxy_send_timeout 600;
    proxy_read_timeout 600;
    send_timeout 600;

    # WebSocket (live job updates)
    location /api/v1/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ~ ^/(docs|redoc|healthz|readyz)$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }

    # Frontend: Next.js static export (trailing-slash routes -> <dir>/index.html)
    root $PROJECT_DIR/frontend/out;
    index index.html;

    location /_next/static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files \$uri \$uri/ \$uri.html /404.html;
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/$SITE_NAME /etc/nginx/sites-enabled/$SITE_NAME
sudo rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/automation
sudo nginx -t
sudo systemctl reload nginx
ok "nginx"

info "services"
sudo systemctl daemon-reload
sudo systemctl enable "$API_SERVICE" "$WORKER_SERVICE" > /dev/null
sudo systemctl restart "$API_SERVICE" "$WORKER_SERVICE"
sleep 5
systemctl is-active "$API_SERVICE" "$WORKER_SERVICE"
curl -fsS "http://127.0.0.1:8000/healthz" && echo
ok "deployed: http://$DOMAIN  (run: sudo certbot --nginx -d $DOMAIN for TLS, then USE_HTTPS=True in backend/.env)"
