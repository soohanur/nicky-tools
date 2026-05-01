# 🚀 Complete Hostinger VPS (KVM2) Deployment Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Overview](#quick-overview)
3. [Step 1: Setup VPS Environment](#step-1-setup-vps-environment)
4. [Step 2: Transfer Project Files](#step-2-transfer-project-files)
5. [Step 3: Configure Environment](#step-3-configure-environment)
6. [Step 4: Install Dependencies](#step-4-install-dependencies)
7. [Step 5: Setup Database](#step-5-setup-database)
8. [Step 6: Build and Deploy](#step-6-build-and-deploy)
9. [Step 7: Configure Nginx](#step-7-configure-nginx)
10. [Step 8: Setup SSL (HTTPS)](#step-8-setup-ssl-https)
11. [Step 9: Configure Systemd Services](#step-9-configure-systemd-services)
12. [Step 10: Testing and Monitoring](#step-10-testing-and-monitoring)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### What You Need
- ✅ Hostinger VPS (KVM2) account
- ✅ Domain name (optional, can use IP address)
- ✅ SSH client (PuTTY for Windows, terminal for Mac/Linux)
- ✅ CompanyInfo.com credentials

### VPS Specifications (KVM2)
```
CPU:        2 vCPU cores
RAM:        8 GB
Storage:    100 GB NVMe SSD
Bandwidth:  8 TB/month
OS:         Ubuntu 22.04 LTS
```

---

## Quick Overview

**Total Time: ~45 minutes**

```
┌──────────────────────────────────────────────────────┐
│           DEPLOYMENT WORKFLOW                         │
├──────────────────────────────────────────────────────┤
│ 1. Setup VPS (10 min)                                │
│ 2. Transfer files (5 min)                            │
│ 3. Configure environment (5 min)                     │
│ 4. Install dependencies (10 min)                     │
│ 5. Setup database (5 min)                            │
│ 6. Deploy application (5 min)                        │
│ 7. Configure Nginx (5 min)                           │
│ 8. Setup SSL (5 min)                                 │
│ 9. Configure services (5 min)                        │
│ 10. Test & Monitor (5 min)                           │
└──────────────────────────────────────────────────────┘
```

---

## Step 1: Setup VPS Environment

### 1.1 Connect to VPS

```bash
# From Windows (PowerShell) or Mac/Linux Terminal
ssh root@your-vps-ip

# Example:
ssh root@123.456.789.012
```

### 1.2 Update System

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git unzip software-properties-common
```

### 1.3 Create Application User

```bash
# Create dedicated user for security
sudo adduser automation
sudo usermod -aG sudo automation

# Switch to automation user
su - automation
```

### 1.4 Create Directory Structure

```bash
# Create project directory
mkdir -p ~/data_info
cd ~/data_info

# Create necessary subdirectories
mkdir -p logs automation_data chrome_profiles
```

---

## Step 2: Transfer Project Files

### Option A: Using SCP (From Windows PowerShell)

```powershell
# On your local Windows machine
cd "E:\Data Info"

# Compress the project (exclude unnecessary files)
# Use 7-Zip or WinRAR to create data_info.zip excluding:
# - node_modules/
# - __pycache__/
# - .git/
# - chrome_profiles/ (large files)
# - logs/
# - *.pyc

# Transfer to VPS
scp data_info.zip automation@your-vps-ip:~/

# Example:
scp data_info.zip automation@123.456.789.012:~/
```

### Option B: Using Git (Recommended if you have a repository)

```bash
# On VPS
cd ~/data_info
git clone https://github.com/yourusername/your-repo.git .
```

### 2.3 Extract Files (if using SCP)

```bash
# On VPS
cd ~/data_info
unzip data_info.zip
rm data_info.zip  # Clean up
```

---

## Step 3: Configure Environment

### 3.1 Configure Backend Environment

```bash
cd ~/data_info
cp .env.production .env
nano .env
```

**Edit the following values:**

```bash
# ⚠️ CHANGE THESE VALUES!

# Your domain or VPS IP
DOMAIN_NAME="your-domain.com"  # or "123.456.789.012"

# Enable HTTPS if you have SSL
USE_HTTPS=True  # Set to False if using IP without SSL

# Security (Generate secure keys!)
SECRET_KEY="$(openssl rand -hex 32)"
ADMIN_SECRET_KEY="$(openssl rand -hex 32)"

# Database credentials
POSTGRES_PASSWORD="$(openssl rand -hex 16)"

# CompanyInfo credentials (⚠️ REQUIRED)
COMPANYINFO_EMAIL="your-email@example.com"
COMPANYINFO_PASSWORD="your-password"

# CORS (Auto-configured based on DOMAIN_NAME)
BACKEND_CORS_ORIGINS="https://your-domain.com,http://your-domain.com"
```

Save and exit: `Ctrl+X`, then `Y`, then `Enter`

### 3.2 Configure Frontend Environment

```bash
cd ~/data_info/frontend
cp .env.production .env.production.local
nano .env.production.local
```

**Edit:**

```bash
# ⚠️ CHANGE THIS!
VITE_API_BASE_URL=https://your-domain.com
VITE_API_URL=https://your-domain.com/api/v1

# If using IP without SSL:
# VITE_API_BASE_URL=http://123.456.789.012
# VITE_API_URL=http://123.456.789.012/api/v1
```

Save and exit.

---

## Step 4: Install Dependencies

### 4.1 Install Python 3.11

```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Set Python 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

### 4.2 Install Node.js 20

```bash
# Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Verify installation
node --version  # Should show v20.x.x
npm --version
```

### 4.3 Install PostgreSQL

```bash
# Install PostgreSQL 15
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 4.4 Install Redis

```bash
# Install Redis
sudo apt install -y redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Find and change: supervised systemd

# Start Redis
sudo systemctl restart redis
sudo systemctl enable redis
```

### 4.5 Install Chrome/Chromium

```bash
# Install Chrome dependencies
sudo apt install -y chromium-browser chromium-chromedriver

# Or install Google Chrome:
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt --fix-broken install -y
```

### 4.6 Install Nginx

```bash
# Install Nginx
sudo apt install -y nginx

# Start Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## Step 5: Setup Database

### 5.1 Create PostgreSQL Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE automation_db;
CREATE USER automation_user WITH ENCRYPTED PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE automation_db TO automation_user;

# Exit PostgreSQL
\q
```

### 5.2 Update Database Password in .env

```bash
nano ~/data_info/.env
# Update POSTGRES_PASSWORD with the password you just created
```

---

## Step 6: Build and Deploy

### 6.1 Install Backend Dependencies

```bash
cd ~/data_info/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
alembic upgrade head
```

### 6.2 Build Frontend

```bash
cd ~/data_info/frontend

# Install dependencies
npm install

# Build for production
npm run build

# The build files will be in: dist/
```

### 6.3 Test Backend

```bash
cd ~/data_info/backend
source venv/bin/activate

# Test the backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+C to stop after verifying it starts
```

---

## Step 7: Configure Nginx

### 7.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/automation
```

**Paste this configuration:**

```nginx
# Backend API Server
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;  # Change this!

    # Increase timeouts for long-running tasks
    proxy_connect_timeout 600;
    proxy_send_timeout 600;
    proxy_read_timeout 600;
    send_timeout 600;

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Support
    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }

    # API Docs
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend
    location / {
        root /home/automation/data_info/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Static files caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        root /home/automation/data_info/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 7.2 Enable Configuration

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/automation /etc/nginx/sites-enabled/

# Remove default configuration
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Step 8: Setup SSL (HTTPS)

### 8.1 Install Certbot

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx
```

### 8.2 Obtain SSL Certificate

```bash
# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Follow the prompts:
# - Enter your email
# - Agree to terms of service
# - Choose whether to redirect HTTP to HTTPS (recommended: Yes)
```

### 8.3 Auto-Renewal

```bash
# Test auto-renewal
sudo certbot renew --dry-run

# Certbot will automatically renew certificates before they expire
```

### 8.4 Update Environment for HTTPS

```bash
nano ~/data_info/.env
# Set: USE_HTTPS=True

nano ~/data_info/frontend/.env.production.local
# Set: VITE_API_BASE_URL=https://your-domain.com
```

---

## Step 9: Configure Systemd Services

### 9.1 Create Backend Service

```bash
sudo nano /etc/systemd/system/automation-backend.service
```

**Paste:**

```ini
[Unit]
Description=Automation Platform Backend API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=automation
Group=automation
WorkingDirectory=/home/automation/data_info/backend
Environment="PATH=/home/automation/data_info/backend/venv/bin"
EnvironmentFile=/home/automation/data_info/.env
ExecStart=/home/automation/data_info/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9.2 Create Celery Worker Service

```bash
sudo nano /etc/systemd/system/automation-celery.service
```

**Paste:**

```ini
[Unit]
Description=Automation Platform Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=automation
Group=automation
WorkingDirectory=/home/automation/data_info/backend
Environment="PATH=/home/automation/data_info/backend/venv/bin"
EnvironmentFile=/home/automation/data_info/.env
ExecStart=/home/automation/data_info/backend/venv/bin/celery -A app.core.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9.3 Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable automation-backend
sudo systemctl enable automation-celery

# Start services
sudo systemctl start automation-backend
sudo systemctl start automation-celery

# Check status
sudo systemctl status automation-backend
sudo systemctl status automation-celery
```

---

## Step 10: Testing and Monitoring

### 10.1 Test API

```bash
# Test health endpoint
curl https://your-domain.com/api/v1/system/health

# Should return: {"status": "healthy"}
```

### 10.2 Access Frontend

Open browser and go to: `https://your-domain.com`

### 10.3 Test WebSocket

1. Register a new user
2. Login
3. Upload a CSV file
4. Start a job
5. Watch for real-time updates

### 10.4 Check Logs

```bash
# Backend logs
sudo journalctl -u automation-backend -f

# Celery logs
sudo journalctl -u automation-celery -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Application logs
tail -f ~/data_info/logs/*.log
```

### 10.5 Monitor Resources

```bash
# Check CPU and Memory
htop

# Check disk usage
df -h

# Check service status
sudo systemctl status automation-backend automation-celery nginx postgresql redis
```

---

## Troubleshooting

### Issue: Backend won't start

```bash
# Check logs
sudo journalctl -u automation-backend -n 50

# Common fixes:
# 1. Check .env file
nano ~/data_info/.env

# 2. Check database connection
sudo -u postgres psql -c "\l"

# 3. Run migrations
cd ~/data_info/backend
source venv/bin/activate
alembic upgrade head

# 4. Restart service
sudo systemctl restart automation-backend
```

### Issue: Celery worker not processing jobs

```bash
# Check Celery logs
sudo journalctl -u automation-celery -n 50

# Check Redis connection
redis-cli ping  # Should return "PONG"

# Restart Celery
sudo systemctl restart automation-celery
```

### Issue: Nginx 502 Bad Gateway

```bash
# Check if backend is running
curl http://localhost:8000/api/v1/system/health

# Check Nginx error log
sudo tail -f /var/log/nginx/error.log

# Restart services
sudo systemctl restart automation-backend
sudo systemctl restart nginx
```

### Issue: WebSocket connection fails

```bash
# Check Nginx WebSocket configuration
sudo nano /etc/nginx/sites-available/automation

# Ensure WebSocket location block is present
# Test Nginx configuration
sudo nginx -t
sudo systemctl reload nginx
```

### Issue: SSL certificate error

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate
sudo certbot renew

# Restart Nginx
sudo systemctl restart nginx
```

### Issue: Chrome/Selenium errors

```bash
# Install Chrome dependencies
sudo apt install -y chromium-browser chromium-chromedriver

# Or reinstall Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt --fix-broken install -y
```

### Issue: Database connection errors

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
sudo -u postgres psql -c "SELECT version();"

# Reset password
sudo -u postgres psql
ALTER USER automation_user WITH PASSWORD 'new-password';
\q

# Update .env file
nano ~/data_info/.env
```

---

## Maintenance Commands

### Update Application

```bash
cd ~/data_info

# Pull latest changes (if using git)
git pull

# Update backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart automation-backend
sudo systemctl restart automation-celery

# Update frontend
cd ../frontend
npm install
npm run build
sudo systemctl reload nginx
```

### Backup Database

```bash
# Create backup
sudo -u postgres pg_dump automation_db > ~/backup_$(date +%Y%m%d).sql

# Restore backup
sudo -u postgres psql automation_db < ~/backup_20240206.sql
```

### View Logs

```bash
# All services
sudo journalctl -u automation-backend -u automation-celery -f

# Last 100 lines
sudo journalctl -u automation-backend -n 100
```

### Restart All Services

```bash
sudo systemctl restart automation-backend
sudo systemctl restart automation-celery
sudo systemctl restart nginx
sudo systemctl restart postgresql
sudo systemctl restart redis
```

---

## Performance Optimization

### For KVM2 (8GB RAM)

```bash
# Optimize PostgreSQL
sudo nano /etc/postgresql/15/main/postgresql.conf
# Change:
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
max_connections = 50

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Optimize Nginx

```bash
sudo nano /etc/nginx/nginx.conf
# Add in http block:
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml;
```

---

## Security Best Practices

1. **Firewall Configuration**

```bash
# Install UFW
sudo apt install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

2. **Disable Root Login**

```bash
sudo nano /etc/ssh/sshd_config
# Change: PermitRootLogin no
sudo systemctl restart sshd
```

3. **Regular Updates**

```bash
# Setup automatic security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

---

## 🎉 Deployment Complete!

Your application should now be running at:
- **Frontend:** https://your-domain.com
- **API Docs:** https://your-domain.com/docs
- **API:** https://your-domain.com/api/v1

### Next Steps:
1. ✅ Register first user account
2. ✅ Test CSV upload and processing
3. ✅ Monitor logs for any issues
4. ✅ Setup regular backups
5. ✅ Configure monitoring alerts

### Support
For issues or questions, check the logs:
```bash
sudo journalctl -u automation-backend -f
sudo journalctl -u automation-celery -f
```

---

**Good luck with your deployment! 🚀**
