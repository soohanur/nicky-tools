#!/bin/bash
# systemd ExecStart for the scraper worker on the VPS.
# Reads MAX_WORKERS from the backend .env so the Settings page can change it.

BACKEND_DIR=/var/www/datainfo/backend
ENV_FILE=$BACKEND_DIR/.env
MAX_WORKERS=1

if [ -f "$ENV_FILE" ]; then
    MAX_WORKERS_LINE=$(grep -E '^MAX_WORKERS=' "$ENV_FILE" | head -n 1)
    if [ -n "$MAX_WORKERS_LINE" ]; then
        MAX_WORKERS=$(echo "$MAX_WORKERS_LINE" | cut -d'=' -f2 | tr -d '[:space:]"')
    fi
fi

if ! [[ "$MAX_WORKERS" =~ ^[0-9]+$ ]]; then
    echo "Invalid MAX_WORKERS value, defaulting to 1"
    MAX_WORKERS=1
fi

echo "Starting Celery with $MAX_WORKERS workers..."

# prefork pool so several jobs can run at once (one Chrome per worker process)
cd "$BACKEND_DIR" || exit 1
exec "$BACKEND_DIR/venv/bin/celery" -A app.worker worker --loglevel=info --concurrency="$MAX_WORKERS" --pool=prefork
