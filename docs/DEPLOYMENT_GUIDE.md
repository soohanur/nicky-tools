# 🚀 Complete Deployment Guide - Hostinger VPS

## 📋 System Overview

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                     Hostinger VPS Server                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Frontend   │  │   Backend    │  │  Automation  │      │
│  │   (React)    │  │   (FastAPI)  │  │   (Selenium) │      │
│  │   Port 3000  │  │   Port 8000  │  │   Headless   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │               │
│         └─────────────────┴──────────────────┘               │
│                          │                                   │
│                  ┌───────▼────────┐                         │
│                  │    Nginx        │                         │
│                  │   Port 80/443   │                         │
│                  └────────────────┘                          │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Data Storage: /home/user/automation_data/           │   │
│  │  - Input CSV files                                   │   │
│  │  - Output CSV files                                  │   │
│  │  - Chrome profile                                    │   │
│  │  - Logs                                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Phase 1: VPS Initial Setup (30 minutes)

### Step 1.1: Connect to Hostinger VPS

```bash
# From your local machine
ssh root@your-vps-ip

# Change default password immediately
passwd
```

### Step 1.2: Create Non-Root User (Security Best Practice)

```bash
# Create automation user
adduser automation
usermod -aG sudo automation

# Switch to new user
su - automation
cd ~
```

### Step 1.3: Update System & Install Core Dependencies

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    python3.11 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    supervisor \
    curl \
    wget \
    unzip \
    software-properties-common \
    build-essential
```

### Step 1.4: Install Chrome & ChromeDriver (Critical for Selenium)

```bash
# Download and install Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb

# Verify installation
google-chrome --version

# Install ChromeDriver dependencies
sudo apt install -y \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    xvfb

# Clean up
rm google-chrome-stable_current_amd64.deb
```

---

## 🏗️ Phase 2: Project Deployment (20 minutes)

### Step 2.1: Create Project Structure

```bash
# Create directories
mkdir -p ~/automation_platform
cd ~/automation_platform

# Create subdirectories
mkdir -p automation_tool
mkdir -p backend
mkdir -p frontend
mkdir -p automation_data/{input,output,logs,chrome_profile}
mkdir -p scripts
```

### Step 2.2: Upload Automation Tool

```bash
# From your local machine (PowerShell)
# Compress the project first
cd "e:\Data Info"
Compress-Archive -Path * -DestinationPath "DataInfo.zip"

# Upload via SCP
scp DataInfo.zip automation@your-vps-ip:~/automation_platform/automation_tool/

# On VPS: Extract
cd ~/automation_platform/automation_tool
unzip DataInfo.zip
rm DataInfo.zip
```

### Step 2.3: Setup Python Virtual Environment

```bash
cd ~/automation_platform/automation_tool

# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
python -c "import selenium; print('Selenium installed:', selenium.__version__)"
```

### Step 2.4: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit configuration
nano .env
```

**Production `.env` Configuration:**
```bash
# Browser Configuration
CHROME_PROFILE_PATH=/home/automation/automation_platform/automation_data/chrome_profile
CHROME_PROFILE_NAME=Default

# CompanyInfo Configuration
COMPANYINFO_URL=https://www.companyinfo.com/search
COMPANYINFO_SEARCH_TIMEOUT=10
COMPANYINFO_EMAIL=your-email@example.com
COMPANYINFO_PASSWORD=your-secure-password

# File Paths (Absolute paths for VPS)
INPUT_EXCEL_PATH=/home/automation/automation_platform/automation_data/input/input.csv
OUTPUT_CSV_PATH=/home/automation/automation_platform/automation_data/output/output.csv
SHEET_NAME=Sheet1

# Column Mappings
COL_COMPANY_NAME=CB
COL_ADDRESS_PART1=CC
COL_ADDRESS_PART2=CD
COL_ADDRESS_PART3=CF
COL_PHONE_OUTPUT=CG
COL_EMAIL_OUTPUT=CH

# Processing Configuration
HEADLESS_MODE=True
IMPLICIT_WAIT=5
PAGE_LOAD_TIMEOUT=30
MAX_WORKERS=1

# Logging
LOG_LEVEL=INFO
```

---

## 🔧 Phase 3: Production Configuration (30 minutes)

### Step 3.1: Create Startup Script

```bash
nano ~/automation_platform/scripts/run_automation.sh
```

**File: `run_automation.sh`**
```bash
#!/bin/bash

# Automation Tool Runner with Error Handling
# Author: Automation Platform Team
# Date: 2026-01-31

set -e  # Exit on error

# Configuration
PROJECT_DIR="/home/automation/automation_platform/automation_tool"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
LOG_FILE="/home/automation/automation_platform/automation_data/logs/automation.log"
PID_FILE="/home/automation/automation_platform/automation.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        warn "Automation is already running (PID: $PID)"
        exit 1
    else
        log "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Health checks
log "Starting automation tool..."

# Check Chrome
if ! command -v google-chrome &> /dev/null; then
    error "Google Chrome not installed"
    exit 1
fi

log "✓ Chrome installed: $(google-chrome --version)"

# Check Python environment
if [ ! -f "$PYTHON" ]; then
    error "Virtual environment not found at $VENV_DIR"
    exit 1
fi

log "✓ Python environment ready"

# Check input file
INPUT_FILE="$PROJECT_DIR/data/input/input.csv"
if [ ! -f "$INPUT_FILE" ]; then
    warn "No input file found at $INPUT_FILE"
fi

# Run automation with virtual display (for headless Chrome)
log "Starting automation process..."
cd "$PROJECT_DIR"

# Store PID
echo $$ > "$PID_FILE"

# Run with xvfb for virtual display
xvfb-run -a --server-args="-screen 0 1920x1080x24" \
    "$PYTHON" src/main.py 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

# Cleanup
rm "$PID_FILE"

if [ $EXIT_CODE -eq 0 ]; then
    log "✓ Automation completed successfully"
else
    error "Automation failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
```

```bash
# Make executable
chmod +x ~/automation_platform/scripts/run_automation.sh
```

### Step 3.2: Create Systemd Service (Auto-Start on Boot)

```bash
sudo nano /etc/systemd/system/automation-tool.service
```

**File: `/etc/systemd/system/automation-tool.service`**
```ini
[Unit]
Description=CompanyInfo Automation Tool
After=network.target

[Service]
Type=simple
User=automation
WorkingDirectory=/home/automation/automation_platform/automation_tool
Environment="DISPLAY=:99"
ExecStart=/home/automation/automation_platform/scripts/run_automation.sh
Restart=on-failure
RestartSec=10
StandardOutput=append:/home/automation/automation_platform/automation_data/logs/service.log
StandardError=append:/home/automation/automation_platform/automation_data/logs/service.log

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable automation-tool.service

# Don't start yet - we'll test manually first
```

### Step 3.3: Setup Cron Jobs (Scheduled Automation)

```bash
crontab -e
```

**Add these lines:**
```bash
# Run automation daily at 2 AM
0 2 * * * /home/automation/automation_platform/scripts/run_automation.sh >> /home/automation/automation_platform/automation_data/logs/cron.log 2>&1

# Clean old logs weekly (Sunday at 3 AM)
0 3 * * 0 find /home/automation/automation_platform/automation_data/logs -name "*.log" -mtime +30 -delete

# Health check every hour (optional)
0 * * * * curl -s http://localhost:8000/health || echo "Backend down" | mail -s "Alert: Backend Down" your-email@example.com
```

---

## 🌐 Phase 4: Backend API Setup (Future-Ready)

### Step 4.1: Create FastAPI Backend

```bash
cd ~/automation_platform/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install FastAPI
pip install fastapi uvicorn python-multipart
```

**Create `main.py`:**
```bash
nano main.py
```

```python
# Backend API for Automation Platform
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import subprocess
import os
from pathlib import Path

app = FastAPI(title="Automation Platform API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
AUTOMATION_DIR = Path("/home/automation/automation_platform/automation_tool")
DATA_DIR = Path("/home/automation/automation_platform/automation_data")
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPT_PATH = Path("/home/automation/automation_platform/scripts/run_automation.sh")

@app.get("/")
async def root():
    return {"message": "Automation Platform API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "chrome": os.path.exists("/usr/bin/google-chrome")}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload input CSV file"""
    file_path = INPUT_DIR / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"message": "File uploaded successfully", "filename": file.filename}

@app.post("/run-automation")
async def run_automation(background_tasks: BackgroundTasks):
    """Trigger automation process"""
    def run_script():
        subprocess.run([str(SCRIPT_PATH)], shell=True)
    
    background_tasks.add_task(run_script)
    return {"message": "Automation started in background"}

@app.get("/download-output/{filename}")
async def download_output(filename: str):
    """Download output CSV file"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}
    return FileResponse(file_path, media_type="text/csv", filename=filename)

@app.get("/list-outputs")
async def list_outputs():
    """List all output files"""
    files = [f.name for f in OUTPUT_DIR.glob("DONE_*.csv")]
    return {"files": files}

@app.get("/logs")
async def get_logs(lines: int = 100):
    """Get recent log lines"""
    log_file = DATA_DIR / "logs" / "automation.log"
    if not log_file.exists():
        return {"logs": []}
    
    with open(log_file, "r") as f:
        log_lines = f.readlines()[-lines:]
    return {"logs": log_lines}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Create systemd service:**
```bash
sudo nano /etc/systemd/system/automation-backend.service
```

```ini
[Unit]
Description=Automation Platform Backend API
After=network.target

[Service]
Type=simple
User=automation
WorkingDirectory=/home/automation/automation_platform/backend
ExecStart=/home/automation/automation_platform/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable automation-backend.service
sudo systemctl start automation-backend.service
```

---

## 🎨 Phase 5: Frontend Setup (Optional for Now)

### Step 5.1: Install Node.js

```bash
# Install Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify
node --version
npm --version
```

### Step 5.2: Create React Frontend (Basic Template)

```bash
cd ~/automation_platform/frontend
npx create-react-app automation-ui
cd automation-ui

# Install dependencies
npm install axios react-dropzone
```

---

## 🔒 Phase 6: Nginx & Security Setup

### Step 6.1: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/automation
```

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Or VPS IP

    # Frontend (React)
    location / {
        root /home/automation/automation_platform/frontend/automation-ui/build;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/automation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6.2: Setup Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Step 6.3: SSL Certificate (Free with Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 🧪 Phase 7: Testing & Verification

### Test 1: Manual Automation Run

```bash
cd ~/automation_platform/automation_tool
source venv/bin/activate

# Create test CSV
cat > data/input/input.csv << EOF
CB,CC,CD,CF,CG,CH
Test Company,123 Main St,,Amsterdam,NULL,NULL
EOF

# Run automation
python src/main.py
```

### Test 2: API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Upload file
curl -X POST -F "file=@test.csv" http://localhost:8000/upload-csv

# Trigger automation
curl -X POST http://localhost:8000/run-automation

# Get logs
curl http://localhost:8000/logs
```

### Test 3: Service Auto-Start

```bash
# Reboot VPS
sudo reboot

# After reboot, check services
sudo systemctl status automation-backend
sudo systemctl status nginx
```

---

## 📊 Phase 8: Monitoring & Maintenance

### Step 8.1: Setup Log Rotation

```bash
sudo nano /etc/logrotate.d/automation
```

```
/home/automation/automation_platform/automation_data/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 automation automation
}
```

### Step 8.2: Monitoring Script

```bash
nano ~/automation_platform/scripts/monitor.sh
```

```bash
#!/bin/bash

# Check services
systemctl is-active --quiet automation-backend && echo "✓ Backend running" || echo "✗ Backend down"
systemctl is-active --quiet nginx && echo "✓ Nginx running" || echo "✗ Nginx down"

# Check disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "⚠ Disk usage high: ${DISK_USAGE}%"
fi

# Check memory
FREE_MEM=$(free -m | awk 'NR==2 {print $4}')
if [ $FREE_MEM -lt 500 ]; then
    echo "⚠ Low memory: ${FREE_MEM}MB free"
fi
```

```bash
chmod +x ~/automation_platform/scripts/monitor.sh

# Add to crontab (every 5 minutes)
*/5 * * * * /home/automation/automation_platform/scripts/monitor.sh >> /home/automation/automation_platform/automation_data/logs/monitor.log 2>&1
```

---

## 🚀 Phase 9: Deployment Checklist

### Pre-Deployment
- [ ] VPS has minimum 2GB RAM
- [ ] Chrome installed and working
- [ ] Python environment activated
- [ ] All dependencies installed
- [ ] .env file configured with correct paths
- [ ] CompanyInfo login credentials set

### Deployment
- [ ] Project uploaded and extracted
- [ ] Startup script tested manually
- [ ] Backend API responding
- [ ] Nginx configured and running
- [ ] Firewall rules set
- [ ] SSL certificate installed (if using domain)

### Post-Deployment
- [ ] Test automation with sample CSV
- [ ] Verify output files generated
- [ ] Check logs for errors
- [ ] Test API endpoints from external IP
- [ ] Setup cron jobs
- [ ] Configure monitoring alerts

---

## 📈 Phase 10: Scaling Strategy

### Current Setup (Single VPS)
```
VPS: 2GB RAM, 1 CPU
- Handles 1-100 companies/day
- Single Chrome instance
- Sequential processing
```

### Scaling to 1000+ Companies/Day
```
VPS: 4GB RAM, 2 CPU
- Parallel processing (MAX_WORKERS=2)
- Chrome tabs for concurrent scraping
- Database for queue management
```

### Scaling to 10,000+ Companies/Day
```
Architecture:
1. Load Balancer (Nginx)
2. Multiple Automation Workers (3-5 VPS)
3. Centralized Database (PostgreSQL)
4. Redis Queue for job distribution
5. S3 storage for CSV files
```

**Future Implementation:**
```python
# Add to requirements.txt
# celery==5.3.4
# redis==5.0.1
# sqlalchemy==2.0.23

# Worker with Celery
from celery import Celery

app = Celery('automation', broker='redis://localhost:6379/0')

@app.task
def process_company(company_data):
    # Run automation for single company
    pass
```

---

## 🛠️ Troubleshooting

### Chrome Won't Start in Headless Mode
```bash
# Install missing dependencies
sudo apt install -y libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1
```

### Permission Denied Errors
```bash
# Fix ownership
sudo chown -R automation:automation /home/automation/automation_platform
chmod -R 755 /home/automation/automation_platform
```

### Service Won't Start
```bash
# Check logs
sudo journalctl -u automation-backend -n 50 --no-pager
sudo journalctl -u automation-tool -n 50 --no-pager

# Test manually
cd ~/automation_platform/automation_tool
source venv/bin/activate
python src/main.py
```

### Out of Memory
```bash
# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 📞 Support & Maintenance

### Daily Tasks
- Check logs for errors
- Verify output files generated
- Monitor disk space

### Weekly Tasks
- Review automation success rate
- Update Chrome if needed
- Backup configuration files

### Monthly Tasks
- System updates: `sudo apt update && sudo apt upgrade`
- Review and optimize performance
- Test disaster recovery

---

## 🎯 Success Metrics

**Key Performance Indicators:**
- ✅ Automation success rate > 95%
- ✅ Average processing time < 30 seconds/company
- ✅ System uptime > 99.5%
- ✅ API response time < 500ms
- ✅ Zero data loss

---

## 📚 Next Steps

1. **Test automation manually** on VPS
2. **Deploy backend API** for remote control
3. **Add frontend dashboard** (Phase 2)
4. **Implement user authentication** (Phase 3)
5. **Add multi-tenancy** (Phase 4)
6. **Scale to multiple workers** (Phase 5)

---

**Deployment Date:** January 31, 2026  
**Status:** Production Ready  
**Version:** 1.0.0
