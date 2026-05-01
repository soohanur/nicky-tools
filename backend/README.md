# Scalable Automation Platform - Backend

## 🎯 Complete Production-Ready Backend

A **scalable, enterprise-grade backend** for automation tools with job queue, real-time updates, and multi-tool support.

### ✨ Key Features

- 🔐 **JWT Authentication** - Secure user authentication and authorization
- 📊 **Job Queue System** - Celery-based background task processing
- 📡 **Real-time Updates** - WebSocket support for live job progress
- 🗄️ **Database** - PostgreSQL with async SQLAlchemy ORM
- 🚀 **Redis Cache** - Fast caching and message broker
- 📁 **File Management** - Upload/download CSV and Excel files
- 📈 **System Monitoring** - Health checks, metrics, and worker status
- 🔄 **Auto Retry** - Intelligent retry logic for failed tasks
- 📝 **Comprehensive Logging** - Track every step of execution
- 🛡️ **Error Handling** - Robust error handling and recovery
- 📚 **API Documentation** - Auto-generated Swagger/ReDoc docs
- 🎨 **Extensible Architecture** - Easy to add new automation tools

### 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│           http://localhost:3000                          │
└──────────────────┬───────────────────────────────────────┘
                   │ REST API + WebSocket
                   ▼
┌──────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (Port 8000)                 │
│  ┌────────────┬──────────────┬─────────────────────┐   │
│  │   Auth     │    Jobs      │      Files          │   │
│  │  System    │  WebSocket   │   Monitoring        │   │
│  └────────────┴──────────────┴─────────────────────┘   │
└──────────────────┬──────────────┬────────────────────────┘
                   │              │
        ┌──────────▼──────────┐  │
        │  PostgreSQL DB      │  │
        │  (Port 5432)        │  │
        └─────────────────────┘  │
                                 │
        ┌────────────────────────▼──────────────────────┐
        │         REDIS (Port 6379)                     │
        │  ┌─────────────┬──────────────────────────┐  │
        │  │ Job Queue   │  Cache & Sessions        │  │
        │  └─────────────┴──────────────────────────┘  │
        └────────────────┬──────────────────────────────┘
                         │
        ┌────────────────▼──────────────────────────────┐
        │         CELERY WORKERS                        │
        │  ┌──────────────────────────────────────┐    │
        │  │  CompanyInfo Scraper (Selenium)      │    │
        │  │  Future: LinkedIn, Email Validator   │    │
        │  └──────────────────────────────────────┘    │
        └───────────────────────────────────────────────┘
```

### 📦 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI 0.109 | High-performance async API |
| **Database** | PostgreSQL 15 | Relational data storage |
| **ORM** | SQLAlchemy 2.0 | Async database operations |
| **Task Queue** | Celery 5.3 | Background job processing |
| **Message Broker** | Redis 7 | Queue & caching |
| **Authentication** | JWT (python-jose) | Secure token-based auth |
| **Password Hash** | bcrypt (passlib) | Secure password storage |
| **WebSocket** | FastAPI WebSocket | Real-time communication |
| **Monitoring** | Flower, psutil | Worker monitoring & metrics |
| **Automation** | Selenium 4.16 | Browser automation |
| **Data Processing** | pandas, openpyxl | CSV/Excel handling |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **PostgreSQL 15+**
- **Redis 7+**
- **Chrome/Chromium** (for Selenium)

### 1. Install Dependencies

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

**Important settings:**

```env
SECRET_KEY="your-secure-random-key-here"
POSTGRES_SERVER="localhost"
POSTGRES_USER="automation_user"
POSTGRES_PASSWORD="your-db-password"
REDIS_HOST="localhost"
COMPANYINFO_EMAIL="your-email@example.com"
COMPANYINFO_PASSWORD="your-password"
```

### 3. Setup Database

```bash
# Create PostgreSQL database
createdb automation_db

# Run migrations
alembic upgrade head
```

### 4. Start Services

**Option A: Using Docker (Recommended)**

```bash
# Start PostgreSQL + Redis
docker-compose up -d

# Start backend
./start_dev.sh  # Linux/Mac
start_dev.bat   # Windows
```

**Option B: Manual Start**

Terminal 1 - Celery Worker:
```bash
celery -A app.core.celery_app worker --loglevel=info --concurrency=2
```

Terminal 2 - Flower (Optional monitoring):
```bash
celery -A app.core.celery_app flower --port=5555
```

Terminal 3 - FastAPI Server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Access Services

- **API Docs (Swagger):** http://localhost:8000/docs
- **API Docs (ReDoc):** http://localhost:8000/redoc
- **Flower Monitor:** http://localhost:5555
- **Health Check:** http://localhost:8000/health

---

## 📚 API Documentation

### Authentication

#### Register
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecurePass123",
  "full_name": "John Doe"
}
```

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=johndoe&password=SecurePass123

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Job Management

#### Create Job
```http
POST /api/v1/jobs
Authorization: Bearer <token>
Content-Type: application/json

{
  "tool_type": "companyinfo_scraper",
  "name": "Extract 100 Companies",
  "description": "Process batch #123",
  "priority": "normal",
  "config": {
    "email": "login@example.com",
    "password": "pass123",
    "headless_mode": true,
    "max_workers": 1
  }
}
```

#### Upload File
```http
POST /api/v1/files/upload?job_uuid=<uuid>
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=@input.csv
```

#### Start Job
```http
POST /api/v1/jobs/{job_uuid}/start
Authorization: Bearer <token>
```

#### Get Job Status
```http
GET /api/v1/jobs/{job_uuid}
Authorization: Bearer <token>

Response:
{
  "id": 1,
  "job_uuid": "abc-123",
  "status": "running",
  "progress": 45.5,
  "total_rows": 100,
  "processed_rows": 45,
  "successful_rows": 43,
  "failed_rows": 2,
  ...
}
```

#### Download Result
```http
GET /api/v1/files/download/{filename}
Authorization: Bearer <token>
```

### WebSocket (Real-time Updates)

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?token=YOUR_JWT_TOKEN');

// Subscribe to job updates
ws.send(JSON.stringify({
  action: 'subscribe',
  job_uuid: 'abc-123'
}));

// Receive updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Job Update:', data);
  // {type: "job_update", job_uuid: "abc-123", data: {...}}
};
```

---

## 🗄️ Database Schema

### Users
- `id` (PK), `email`, `username`, `hashed_password`
- `is_active`, `is_superuser`
- `created_at`, `updated_at`

### Jobs
- `id` (PK), `job_uuid` (unique), `user_id` (FK)
- `tool_type`, `name`, `description`
- `status`, `priority`, `progress`
- `input_file_path`, `output_file_path`, `config`
- `total_rows`, `processed_rows`, `successful_rows`, `failed_rows`
- `created_at`, `started_at`, `completed_at`
- `error_message`, `retry_count`

### Job Logs
- `id` (PK), `job_id` (FK)
- `timestamp`, `level`, `message`, `metadata`

---

## 🔧 Adding New Tools

The backend is designed for easy extensibility. To add a new automation tool:

### 1. Update Tool Enum

```python
# app/db/models.py
class ToolType(str, enum.Enum):
    COMPANYINFO_SCRAPER = "companyinfo_scraper"
    LINKEDIN_SCRAPER = "linkedin_scraper"  # NEW TOOL
```

### 2. Create Task Function

```python
# app/tasks/automation_tasks.py
@celery_app.task(base=JobTask, bind=True, name="run_linkedin_scraper")
def run_linkedin_scraper(self, job_uuid, input_file, output_file, config):
    # Your automation logic here
    pass
```

### 3. Update Router

```python
# app/tasks/automation_tasks.py - run_automation_job()
if tool_type == "linkedin_scraper":
    return run_linkedin_scraper(...)
```

### 4. Create Config Schema (Optional)

```python
# app/schemas/schemas.py
class LinkedInConfig(JobConfigBase):
    login_email: str
    login_password: str
    search_keywords: List[str]
```

**That's it!** The entire infrastructure (API, database, queue, monitoring) works automatically.

---

## 📊 Monitoring & Operations

### Health Check

```bash
curl http://localhost:8000/api/v1/system/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-02-01T...",
  "database": "healthy",
  "redis": "healthy",
  "celery": "healthy (2 workers)"
}
```

### System Stats

```bash
curl http://localhost:8000/api/v1/system/stats
```

Response:
```json
{
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  "disk_percent": 34.5,
  "active_jobs": 2,
  "queued_jobs": 5,
  "completed_jobs_today": 150,
  "failed_jobs_today": 3,
  "success_rate": 98.04
}
```

### Worker Status

```bash
curl http://localhost:8000/api/v1/system/workers
```

### Flower UI

Open http://localhost:5555 for visual monitoring:
- Active tasks
- Worker status
- Task history
- Success/failure rates

---

## 🐳 Docker Deployment

### docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: automation_db
      POSTGRES_USER: automation_user
      POSTGRES_PASSWORD: automation_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=postgresql+asyncpg://automation_user:automation_password@postgres/automation_db
      - REDIS_URL=redis://redis:6379/0

  celery:
    build: .
    command: celery -A app.core.celery_app worker --loglevel=info
    depends_on:
      - postgres
      - redis

  flower:
    build: .
    command: celery -A app.core.celery_app flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis

volumes:
  postgres_data:
```

---

## 🛡️ Security Best Practices

1. **Change SECRET_KEY** in production (use `openssl rand -hex 32`)
2. **Use environment variables** for sensitive data
3. **Enable HTTPS** with SSL certificates
4. **Set strong database passwords**
5. **Limit CORS origins** to your frontend domain
6. **Enable rate limiting** (already included)
7. **Use Sentry** for error tracking (optional)
8. **Regular backups** of PostgreSQL database

---

## 📈 Performance Optimization

### Current Capacity (KVM 2)
- **2 vCPU cores:** Run 2 Celery workers
- **8 GB RAM:** Supports 1-3 parallel browser instances
- **100 GB NVMe:** Fast file I/O

### Scaling Options

1. **Horizontal Scaling:**
   - Add more Celery workers on separate machines
   - Use Redis Sentinel for HA

2. **Vertical Scaling:**
   - Increase VPS resources
   - Add SSD cache

3. **Database Optimization:**
   - Connection pooling (already configured)
   - Query optimization
   - Read replicas

---

## 🐛 Troubleshooting

### Database Connection Error
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432
```

### Redis Connection Error
```bash
# Check Redis is running
redis-cli ping
```

### Celery Workers Not Starting
```bash
# Check Celery can connect to Redis
celery -A app.core.celery_app inspect ping
```

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>
```

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📞 Support

- **Documentation:** http://localhost:8000/docs
- **Issues:** GitHub Issues
- **Email:** support@yourdomain.com

---

**Built with ❤️ for scalable automation**
