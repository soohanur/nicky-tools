@echo off
REM Backend Startup Script for Windows Development

echo ========================================
echo Starting Automation Platform Backend...
echo ========================================

REM Check if .env exists
if not exist ".env" (
    echo WARNING: No .env file found. Creating from template...
    copy .env.example .env
    echo .env created. Please configure before continuing.
    exit /b 1
)

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

echo.
echo Starting backend services...
echo ----------------------------

REM Start Redis if Docker is available
docker version >nul 2>&1
if %errorlevel% == 0 (
    echo Starting Redis...
    docker run -d --name automation_redis -p 6379:6379 redis:7-alpine >nul 2>&1
    
    echo Starting PostgreSQL...
    docker run -d --name automation_postgres -e POSTGRES_USER=automation_user -e POSTGRES_PASSWORD=automation_password -e POSTGRES_DB=automation_db -p 5432:5432 postgres:15-alpine >nul 2>&1
)

echo.
echo Waiting for services...
timeout /t 3 /nobreak >nul

REM Run database migrations
echo.
echo Running database migrations...
alembic upgrade head

REM Start services in background
echo.
echo Starting Celery worker...
start "Celery Worker" celery -A app.core.celery_app worker --loglevel=info --concurrency=2 --pool=solo

echo Starting Flower (Celery UI)...
start "Flower" celery -A app.core.celery_app flower --port=5555

echo Starting FastAPI server...
start "FastAPI" uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo Backend started successfully!
echo ========================================
echo.
echo API Documentation: http://localhost:8000/docs
echo API Alternative:   http://localhost:8000/redoc
echo Flower Monitor:    http://localhost:5555
echo Health Check:      http://localhost:8000/health
echo.
echo Press any key to stop all services...
pause >nul

REM Cleanup
taskkill /FI "WindowTitle eq Celery Worker*" /F >nul 2>&1
taskkill /FI "WindowTitle eq Flower*" /F >nul 2>&1
taskkill /FI "WindowTitle eq FastAPI*" /F >nul 2>&1

echo.
echo Services stopped.
