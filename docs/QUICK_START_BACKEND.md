# 🎯 Quick Start Guide - Get Running in 10 Minutes

## ⚡ Fastest Path to Running Backend

### **Option 1: Docker (Recommended - 5 Commands)**

```bash
# 1. Navigate to backend
cd backend

# 2. Create environment file
cp .env.example .env

# 3. Edit .env (Windows: notepad .env, Linux: nano .env)
# Set these required fields:
#   COMPANYINFO_EMAIL=your-email@example.com
#   COMPANYINFO_PASSWORD=your-password
#   SECRET_KEY=your-random-secret-key-here

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps
```

**Done!** Services running:
- ✅ API: http://localhost:8000/docs
- ✅ Flower: http://localhost:5555
- ✅ PostgreSQL: localhost:5432
- ✅ Redis: localhost:6379

---

### **Option 2: Windows (No Docker)**

```powershell
# 1. Install PostgreSQL
# Download from: https://www.postgresql.org/download/windows/
# During install, set password to: automation_password

# 2. Install Redis
# Download from: https://github.com/tporadowski/redis/releases
# Extract and run: redis-server.exe

# 3. Navigate to backend
cd backend

# 4. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Setup environment
copy .env.example .env
# Edit .env with your settings

# 7. Create database
# Open pgAdmin or psql and run:
#   CREATE DATABASE automation_db;

# 8. Run migrations
alembic upgrade head

# 9. Start everything
start_dev.bat
```

---

### **Option 3: Linux/Mac (No Docker)**

```bash
# 1. Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib  # Ubuntu/Debian
# OR
brew install postgresql  # Mac

# 2. Install Redis
sudo apt install redis-server  # Ubuntu/Debian
# OR
brew install redis  # Mac

# 3. Start services
sudo systemctl start postgresql redis  # Ubuntu/Debian
# OR
brew services start postgresql redis  # Mac

# 4. Create database
sudo -u postgres psql
CREATE DATABASE automation_db;
CREATE USER automation_user WITH PASSWORD 'automation_password';
GRANT ALL PRIVILEGES ON DATABASE automation_db TO automation_user;
\q

# 5. Navigate to backend
cd backend

# 6. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 7. Install dependencies
pip install -r requirements.txt

# 8. Setup environment
cp .env.example .env
# Edit .env with: nano .env

# 9. Run migrations
alembic upgrade head

# 10. Start everything
chmod +x start_dev.sh
./start_dev.sh
```

---

## 🧪 Test Your Backend

### **1. Check Health**

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","version":"1.0.0"}
```

### **2. Open API Docs**

Open browser: http://localhost:8000/docs

You should see Swagger UI with all endpoints.

### **3. Run Test Suite**

```bash
cd backend
pip install httpx  # If not already installed
python test_backend.py
```

Should see:
```
✅ Health Check passed
✅ System Health passed
✅ User Registration passed
✅ User Login passed
...
🎉 ALL TESTS PASSED! Backend is fully functional.
```

---

## 📝 First API Call

### **1. Register User**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "TestPass123",
    "full_name": "Test User"
  }'
```

### **2. Login**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=TestPass123"
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

**Copy the `access_token`** - you'll need it for authenticated requests.

### **3. Create Job**

```bash
TOKEN="your-access-token-here"

curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_type": "companyinfo_scraper",
    "name": "Test Job",
    "priority": "normal",
    "config": {
      "email": "your-companyinfo-email",
      "password": "your-companyinfo-password",
      "headless_mode": true
    }
  }'
```

Response will include `job_uuid` - use this to track the job.

---

## 🐛 Troubleshooting

### **Port Already in Use**

```bash
# Find process using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Linux/Mac

# Kill process
taskkill /F /PID <PID>  # Windows
kill -9 <PID>  # Linux/Mac
```

### **Database Connection Error**

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432  # Linux/Mac

# Check service status
sudo systemctl status postgresql  # Linux
brew services list  # Mac

# Restart if needed
sudo systemctl restart postgresql  # Linux
brew services restart postgresql  # Mac
```

### **Redis Connection Error**

```bash
# Check Redis is running
redis-cli ping  # Should return: PONG

# Check service status
sudo systemctl status redis  # Linux
brew services list  # Mac

# Restart if needed
sudo systemctl restart redis  # Linux
brew services restart redis  # Mac
```

### **Celery Worker Not Starting**

```bash
# Check Redis connection first
redis-cli ping

# Try manual start
celery -A app.core.celery_app worker --loglevel=debug

# Check for errors in output
```

### **Alembic Migration Error**

```bash
# Reset migrations (development only!)
alembic downgrade base
alembic upgrade head

# Or recreate database
dropdb automation_db
createdb automation_db
alembic upgrade head
```

---

## 🔧 Configuration Tips

### **Minimum .env Settings**

```env
# Security (CHANGE IN PRODUCTION!)
SECRET_KEY="your-random-secret-key-minimum-32-chars"

# CompanyInfo Credentials
COMPANYINFO_EMAIL="your-email@example.com"
COMPANYINFO_PASSWORD="your-password"

# Everything else can use defaults for local development
```

### **Generate Secure SECRET_KEY**

```bash
# Python
python -c "import secrets; print(secrets.token_hex(32))"

# OpenSSL
openssl rand -hex 32

# PowerShell
[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

---

## 📊 Verify Everything Works

### **1. Check Services**

```bash
# Docker
docker-compose ps

# Expected output:
# automation_postgres    running   0.0.0.0:5432->5432/tcp
# automation_redis       running   0.0.0.0:6379->6379/tcp
# automation_backend     running   0.0.0.0:8000->8000/tcp
# automation_celery      running
# automation_flower      running   0.0.0.0:5555->5555/tcp
```

### **2. Check Logs**

```bash
# Docker - All logs
docker-compose logs -f

# Docker - Specific service
docker-compose logs -f backend
docker-compose logs -f celery

# Manual - Backend
tail -f ../automation_data/logs/automation.log
```

### **3. Check Database**

```bash
# Connect to PostgreSQL
psql -U automation_user -d automation_db

# List tables
\dt

# Should see:
# users, jobs, job_logs, api_keys, system_metrics, tool_configs
```

---

## 🎯 Next Steps

Once everything is running:

1. **Explore API Docs:** http://localhost:8000/docs
   - Try the "Try it out" button on each endpoint
   - See request/response examples
   - Test authentication flow

2. **Check Flower:** http://localhost:5555
   - Monitor Celery workers
   - See task history
   - View worker stats

3. **Create First Job:**
   - Register user via API
   - Login to get JWT token
   - Create job
   - Upload CSV file
   - Start job
   - Monitor progress

4. **Deploy to VPS:**
   - Follow [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)
   - Use KVM2_ARCHITECTURE.md for Hostinger setup

---

## ✅ Success Checklist

- [ ] Backend running on http://localhost:8000
- [ ] API docs accessible at /docs
- [ ] Health check returns "healthy"
- [ ] PostgreSQL connection working
- [ ] Redis connection working
- [ ] Celery worker active (check Flower)
- [ ] Can register new user
- [ ] Can login and get JWT token
- [ ] Can create job
- [ ] Test suite passes

**All checked?** 🎉 Your backend is fully operational!

---

## 💡 Pro Tips

### **1. Use Swagger UI for Testing**

Instead of curl, use http://localhost:8000/docs:
- Click endpoint → "Try it out"
- Fill in parameters
- Click "Execute"
- See response

### **2. Keep Flower Open**

Monitor workers in real-time at http://localhost:5555

### **3. Use Docker for Development**

Easiest way to manage all services:
```bash
docker-compose up -d    # Start
docker-compose down     # Stop
docker-compose restart  # Restart
docker-compose logs -f  # View logs
```

### **4. Database Backup**

```bash
# Backup
pg_dump -U automation_user automation_db > backup.sql

# Restore
psql -U automation_user automation_db < backup.sql
```

---

**Need help?** Check [backend/README.md](backend/README.md) for detailed documentation!
