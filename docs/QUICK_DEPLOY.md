# 🚀 Quick Start Deployment Guide

## Overview
This guide will help you deploy the Automation Platform to Hostinger VPS (KVM2) in ~45 minutes.

---

## 📋 Pre-Deployment Checklist

### What You Need
- [ ] Hostinger VPS (KVM2) access
- [ ] Domain name (or will use VPS IP)
- [ ] SSH client installed
- [ ] CompanyInfo.com login credentials
- [ ] Project files ready to transfer

### Files Required
```
data_info/
├── .env.production          ← Backend environment template
├── frontend/.env.production ← Frontend environment template
├── vps_setup.sh            ← VPS setup script
├── deploy.sh               ← Deployment script
├── backend/                ← Backend code
├── frontend/               ← Frontend code
└── scraply/                ← Scraply tool
```

---

## 🎯 Deployment Steps

### Step 1: Access Your VPS (2 minutes)

```bash
# Connect via SSH
ssh root@your-vps-ip

# Example:
ssh root@123.456.789.012
```

### Step 2: Run VPS Setup Script (10 minutes)

```bash
# Download and run setup script
# Option A: If you have the script on VPS
chmod +x vps_setup.sh
sudo bash vps_setup.sh

# Option B: Download from your repository
wget https://your-repo.com/vps_setup.sh
chmod +x vps_setup.sh
sudo bash vps_setup.sh
```

**What this does:**
- ✅ Updates system packages
- ✅ Installs Python 3.11
- ✅ Installs Node.js 20
- ✅ Installs PostgreSQL 15
- ✅ Installs Redis
- ✅ Installs Google Chrome
- ✅ Installs Nginx
- ✅ Installs Certbot (SSL)
- ✅ Configures firewall

### Step 3: Create Application User (2 minutes)

```bash
# Create user
sudo adduser automation
# Enter password and details when prompted

# Add to sudo group
sudo usermod -aG sudo automation

# Switch to user
su - automation
```

### Step 4: Transfer Project Files (5 minutes)

**From your Windows machine:**

```powershell
# Method 1: Using SCP
# First, create a zip of your project
cd "E:\Data Info"
# Use 7-Zip or WinRAR to create data_info.zip

# Transfer to VPS
scp data_info.zip automation@your-vps-ip:~/

# Method 2: Using Git
# Push your code to GitHub/GitLab first, then on VPS:
git clone https://github.com/yourusername/data_info.git ~/data_info
```

**On VPS (if using zip):**

```bash
cd ~
unzip data_info.zip
mv data_info ~/data_info  # If needed
cd ~/data_info
```

### Step 5: Configure Environment (5 minutes)

```bash
cd ~/data_info

# Copy production template
cp .env.production .env

# Edit environment file
nano .env
```

**Required Changes:**

```bash
# ⚠️ MUST CHANGE THESE:
DOMAIN_NAME="your-domain.com"           # Or your VPS IP
SECRET_KEY="<generate-with-openssl>"    # See below
POSTGRES_PASSWORD="<strong-password>"   # See below
ADMIN_SECRET_KEY="<admin-password>"     # See below
COMPANYINFO_EMAIL="your@email.com"      # Your credentials
COMPANYINFO_PASSWORD="your-password"    # Your credentials
```

**Generate Secure Keys:**

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate POSTGRES_PASSWORD
openssl rand -hex 16

# Generate ADMIN_SECRET_KEY
openssl rand -hex 16
```

**Save and Exit:** `Ctrl+X`, then `Y`, then `Enter`

### Step 6: Configure Frontend (2 minutes)

```bash
cd ~/data_info/frontend
cp .env.production .env.production.local
nano .env.production.local
```

**Update:**

```bash
# With domain:
VITE_API_BASE_URL=https://your-domain.com
VITE_API_URL=https://your-domain.com/api/v1

# Or with IP (no SSL yet):
VITE_API_BASE_URL=http://123.456.789.012
VITE_API_URL=http://123.456.789.012/api/v1
```

### Step 7: Run Deployment Script (15 minutes)

```bash
cd ~/data_info

# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

**What this does:**
- ✅ Creates PostgreSQL database
- ✅ Installs Python dependencies
- ✅ Runs database migrations
- ✅ Creates necessary directories
- ✅ Builds frontend
- ✅ Creates systemd services
- ✅ Configures Nginx
- ✅ Starts all services

### Step 8: Setup SSL (Optional, 5 minutes)

**If you have a domain:**

```bash
# Install SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Follow prompts:
# - Enter email
# - Agree to terms
# - Choose redirect HTTP to HTTPS (Yes)
```

**Update configuration for HTTPS:**

```bash
# Update backend .env
nano ~/data_info/.env
# Change: USE_HTTPS=True

# Update frontend .env
nano ~/data_info/frontend/.env.production.local
# Change: VITE_API_BASE_URL=https://your-domain.com

# Rebuild frontend
cd ~/data_info/frontend
npm run build

# Restart services
sudo systemctl restart automation-backend
sudo systemctl restart nginx
```

### Step 9: Test Everything (5 minutes)

```bash
# Test backend health
curl http://your-domain.com/api/v1/system/health

# Should return:
# {"status":"healthy"}

# Check service status
sudo systemctl status automation-backend
sudo systemctl status automation-celery

# View logs
sudo journalctl -u automation-backend -n 20
sudo journalctl -u automation-celery -n 20
```

### Step 10: Access Your Application

Open your browser and go to:
- **Frontend:** `https://your-domain.com` (or `http://your-vps-ip`)
- **API Docs:** `https://your-domain.com/docs`

---

## 🎉 You're Done!

### First Steps After Deployment:

1. **Register First User**
   - Go to your domain
   - Click "Register"
   - Create admin account

2. **Test CSV Upload**
   - Upload a sample CSV file
   - Start a job
   - Watch real-time progress

3. **Monitor Services**
   ```bash
   # View logs
   sudo journalctl -u automation-backend -f
   sudo journalctl -u automation-celery -f
   ```

---

## 🔧 Common Commands

### Restart Services
```bash
sudo systemctl restart automation-backend
sudo systemctl restart automation-celery
sudo systemctl restart nginx
```

### View Logs
```bash
# Backend logs
sudo journalctl -u automation-backend -f

# Celery logs
sudo journalctl -u automation-celery -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Check Status
```bash
sudo systemctl status automation-backend
sudo systemctl status automation-celery
sudo systemctl status postgresql
sudo systemctl status redis
sudo systemctl status nginx
```

### Update Application
```bash
cd ~/data_info
git pull  # If using git
cd frontend
npm install
npm run build
cd ../backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart automation-backend
sudo systemctl restart automation-celery
```

---

## 🆘 Quick Troubleshooting

### Backend won't start
```bash
# Check logs
sudo journalctl -u automation-backend -n 50

# Check .env file
nano ~/data_info/.env

# Restart
sudo systemctl restart automation-backend
```

### Celery not processing jobs
```bash
# Check logs
sudo journalctl -u automation-celery -n 50

# Check Redis
redis-cli ping

# Restart
sudo systemctl restart automation-celery
```

### 502 Bad Gateway
```bash
# Check if backend is running
sudo systemctl status automation-backend

# Test locally
curl http://localhost:8000/api/v1/system/health

# Restart everything
sudo systemctl restart automation-backend
sudo systemctl restart nginx
```

### Database connection error
```bash
# Check PostgreSQL
sudo systemctl status postgresql

# Test connection
sudo -u postgres psql -c "\l"

# Check credentials in .env
nano ~/data_info/.env
```

---

## 📊 Resource Monitoring

### Check System Resources
```bash
# CPU and Memory
htop

# Disk usage
df -h

# Process list
ps aux | grep -E "(uvicorn|celery|nginx)"
```

### Monitor Application
```bash
# All services status
systemctl status automation-backend automation-celery nginx postgresql redis

# Real-time logs
sudo journalctl -u automation-backend -u automation-celery -f
```

---

## 🔒 Security Checklist

- [ ] Changed SECRET_KEY in .env
- [ ] Changed POSTGRES_PASSWORD
- [ ] Changed ADMIN_SECRET_KEY
- [ ] Setup SSL with Certbot
- [ ] Configured firewall (UFW)
- [ ] Disabled root SSH login (optional)
- [ ] Setup automatic security updates

---

## 📞 Need Help?

1. **Check Logs First:**
   ```bash
   sudo journalctl -u automation-backend -n 100
   sudo journalctl -u automation-celery -n 100
   ```

2. **Review Configuration:**
   - Check .env file
   - Verify database credentials
   - Confirm CompanyInfo credentials

3. **Test Components:**
   - PostgreSQL: `sudo systemctl status postgresql`
   - Redis: `redis-cli ping`
   - Backend: `curl http://localhost:8000/api/v1/system/health`

---

## 📚 Additional Resources

- [Full Deployment Guide](./HOSTINGER_DEPLOYMENT_GUIDE.md)
- [Backend Documentation](./backend/README.md)
- [Frontend Documentation](./frontend/README.md)
- [Troubleshooting Guide](./HOSTINGER_DEPLOYMENT_GUIDE.md#troubleshooting)

---

**Happy Deploying! 🚀**
