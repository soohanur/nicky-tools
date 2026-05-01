#!/bin/bash

# Safely read MAX_WORKERS from .env file (avoiding bracket parsing issues)
ENV_FILE=/var/www/datainfo/backend/.env
MAX_WORKERS=1

# Parse .env file safely - only extract MAX_WORKERS value
if [ -f "$ENV_FILE" ]; then
    # Use grep to find MAX_WORKERS line and extract value
    MAX_WORKERS_LINE=$(grep -E '^MAX_WORKERS=' "$ENV_FILE" | head -n 1)
    if [ -n "$MAX_WORKERS_LINE" ]; then
        # Extract value after = sign
        MAX_WORKERS=$(echo "$MAX_WORKERS_LINE" | cut -d'=' -f2 | tr -d '[:space:]"')
    fi
fi

# Validate MAX_WORKERS is a number
if ! [[ "$MAX_WORKERS" =~ ^[0-9]+$ ]]; then
    echo "Invalid MAX_WORKERS value, defaulting to 1"
    MAX_WORKERS=1
fi

echo "Starting Celery with $MAX_WORKERS workers..."

# Start Celery with configured worker count
# Using prefork pool to allow parallel job execution (multiple users can run jobs simultaneously)
exec /var/www/datainfo/backend/venv/bin/celery -A app.core.celery_app worker --loglevel=info --concurrency=$MAX_WORKERS --pool=prefork
