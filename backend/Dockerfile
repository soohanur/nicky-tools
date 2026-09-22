# FastAPI API image. The scraper engine (<repo>/scraply) is mounted at /app/scraply
# by docker-compose; the worker image (Dockerfile.worker) adds Chrome.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/scraply

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app + migrations + ops scripts
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
