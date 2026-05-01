#!/bin/bash
# Backend Startup Script for Development

echo "🚀 Starting Automation Platform Backend..."
echo "==========================================="

# Activate virtual environment if exists
if [ -d "venv" ]; then
    echo "✓ Activating virtual environment..."
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "✓ .env created. Please configure before continuing."
    exit 1
fi

# Start services
echo ""
echo "Starting backend services..."
echo "----------------------------"

# 1. Start PostgreSQL (if using Docker)
if command -v docker &> /dev/null; then
    echo "Starting PostgreSQL..."
    docker run -d \
        --name automation_postgres \
        -e POSTGRES_USER=automation_user \
        -e POSTGRES_PASSWORD=automation_password \
        -e POSTGRES_DB=automation_db \
        -p 5432:5432 \
        postgres:15-alpine 2>/dev/null || echo "PostgreSQL already running"
fi

# 2. Start Redis (if using Docker)
if command -v docker &> /dev/null; then
    echo "Starting Redis..."
    docker run -d \
        --name automation_redis \
        -p 6379:6379 \
        redis:7-alpine 2>/dev/null || echo "Redis already running"
fi

echo ""
echo "Waiting for services to be ready..."
sleep 3

# 3. Run database migrations
echo ""
echo "Running database migrations..."
alembic upgrade head

# 4. Start Celery worker
echo ""
echo "Starting Celery worker..."
celery -A app.core.celery_app worker --loglevel=info --concurrency=2 &
CELERY_PID=$!

# 5. Start Flower (Celery monitoring)
echo "Starting Flower (Celery UI)..."
celery -A app.core.celery_app flower --port=5555 &
FLOWER_PID=$!

# 6. Start FastAPI server
echo ""
echo "Starting FastAPI server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait a bit
sleep 2

echo ""
echo "==========================================="
echo "✅ Backend started successfully!"
echo "==========================================="
echo ""
echo "📚 API Documentation: http://localhost:8000/docs"
echo "📊 API Alternative:   http://localhost:8000/redoc"
echo "🌸 Flower Monitor:    http://localhost:5555"
echo "🔐 Health Check:      http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $API_PID 2>/dev/null
    kill $CELERY_PID 2>/dev/null
    kill $FLOWER_PID 2>/dev/null
    echo "✓ Shutdown complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for services
wait
