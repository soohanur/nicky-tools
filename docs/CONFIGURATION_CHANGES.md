# 🔄 Environment Configuration Changes Summary

## Overview
The project has been updated with a **dynamic URL configuration system** that automatically adapts to different environments (development, staging, production). No more hardcoded localhost URLs!

---

## 🎯 What Changed

### 1. **New Configuration System**

#### Backend
- ✅ Created `backend/app/core/environment.py` - Smart environment detection utility
- ✅ Updated `backend/app/core/config.py` - Uses environment utility for dynamic URLs
- ✅ Updated `backend/app/main.py` - Shows environment info on startup

#### Frontend
- ✅ Updated `frontend/src/lib/config/env.ts` - Auto-detects API URL based on environment
- ✅ Updated `frontend/src/lib/services/websocket.ts` - Uses dynamic WebSocket URLs
- ✅ Updated Controls components - Uses config instead of hardcoded URLs

### 2. **New Environment Files**

```
.env.production                    ← Backend production config
frontend/.env.production           ← Frontend production config
```

### 3. **New Deployment Files**

```
HOSTINGER_DEPLOYMENT_GUIDE.md     ← Complete step-by-step guide
QUICK_DEPLOY.md                   ← Quick reference guide
vps_setup.sh                      ← VPS environment setup script
deploy.sh                         ← Application deployment script
```

---

## 🔧 How It Works

### Backend URL Detection

The backend now uses the `EnvironmentConfig` class to automatically detect:

1. **Environment Type** (development/production/docker)
2. **Domain/IP** from `DOMAIN_NAME` environment variable
3. **Protocol** (http/https) based on `USE_HTTPS` setting
4. **CORS Origins** - Auto-generated based on domain

**Example:**

```python
from app.core.environment import EnvironmentConfig

# Automatically adapts to environment
backend_url = EnvironmentConfig.get_backend_url()
# Development: http://localhost:8000
# Production: https://your-domain.com

websocket_url = EnvironmentConfig.get_websocket_url()
# Development: ws://localhost:8000
# Production: wss://your-domain.com
```

### Frontend URL Detection

The frontend automatically detects the API URL:

1. **Checks** `VITE_API_URL` environment variable
2. **Falls back** to `VITE_API_BASE_URL` + `/api/v1`
3. **Production mode**: Uses same domain as frontend
4. **Development mode**: Uses `localhost:8000`

**Example:**

```typescript
// Automatically adapts to environment
const config = {
  API_BASE_URL: getApiBaseUrl(),
  // Development: http://localhost:8000/api/v1
  // Production: https://your-domain.com/api/v1
  
  WS_BASE_URL: getWebSocketUrl(),
  // Development: ws://localhost:8000
  // Production: wss://your-domain.com
}
```

---

## 📝 Configuration Examples

### Local Development (Default)

**No configuration needed!** Just run:

```bash
# Backend
cd backend
python -m uvicorn app.main:app

# Frontend
cd frontend
npm run dev
```

Everything uses `localhost` automatically.

### Production with Domain

**Backend .env:**
```bash
DOMAIN_NAME="your-domain.com"
USE_HTTPS=True
ENVIRONMENT="production"
```

**Frontend .env.production.local:**
```bash
VITE_API_BASE_URL=https://your-domain.com
VITE_API_URL=https://your-domain.com/api/v1
```

### Production with IP (No Domain)

**Backend .env:**
```bash
DOMAIN_NAME="123.456.789.012"
USE_HTTPS=False
ENVIRONMENT="production"
```

**Frontend .env.production.local:**
```bash
VITE_API_BASE_URL=http://123.456.789.012
VITE_API_URL=http://123.456.789.012/api/v1
```

### Docker Compose

**Backend .env:**
```bash
DOMAIN_NAME="localhost"
ENVIRONMENT="docker"
# Uses docker service names internally
# Exposes on localhost externally
```

---

## 🚀 Benefits

### 1. **Zero Localhost Hardcoding**
- No more manual URL changes
- Automatic environment detection
- Works seamlessly across dev/staging/production

### 2. **Easy Deployment**
- Single `.env` file configuration
- Automatic CORS configuration
- Automatic WebSocket URL detection

### 3. **Flexible Hosting**
- Works with domain names
- Works with IP addresses
- Works with Docker
- Works with reverse proxies (Nginx)

### 4. **SSL Support**
- Automatic https/wss detection
- Configurable via `USE_HTTPS` flag
- Certificate-based detection

---

## 🔄 Migration Guide

### If You Have an Existing Deployment

#### 1. Update Backend Configuration

```bash
cd backend
cp .env.production .env

# Edit .env
nano .env

# Add these new variables:
DOMAIN_NAME="your-domain.com"
USE_HTTPS=True
ENVIRONMENT="production"
```

#### 2. Update Frontend Configuration

```bash
cd frontend
cp .env.production .env.production.local

# Edit .env.production.local
nano .env.production.local

# Update:
VITE_API_BASE_URL=https://your-domain.com
VITE_API_URL=https://your-domain.com/api/v1
```

#### 3. Rebuild and Restart

```bash
# Rebuild frontend
cd frontend
npm run build

# Restart backend
sudo systemctl restart automation-backend

# Reload Nginx
sudo systemctl reload nginx
```

---

## 🧪 Testing the Configuration

### Test Backend Environment Detection

```bash
cd backend
source venv/bin/activate
python -c "from app.core.environment import EnvironmentConfig; EnvironmentConfig.print_environment_info()"
```

**Output:**
```
============================================================
🌍 ENVIRONMENT CONFIGURATION
============================================================
Environment:     production
Domain:          your-domain.com
Protocol:        https
Backend URL:     https://your-domain.com
Frontend URL:    https://your-domain.com
WebSocket URL:   wss://your-domain.com
API Docs:        https://your-domain.com/docs
CORS Origins:    4 origins
  - https://your-domain.com
  - https://www.your-domain.com
  - http://your-domain.com
  - http://www.your-domain.com
============================================================
```

### Test Frontend Configuration

```bash
cd frontend
npm run dev

# Check browser console for:
# "API_BASE_URL: https://your-domain.com/api/v1"
# "WS_BASE_URL: wss://your-domain.com"
```

### Test API Access

```bash
# Test health endpoint
curl https://your-domain.com/api/v1/system/health

# Should return:
{"status":"healthy"}
```

---

## 📋 Checklist for Production

- [ ] Set `DOMAIN_NAME` in backend `.env`
- [ ] Set `USE_HTTPS=True` if using SSL
- [ ] Set `ENVIRONMENT=production`
- [ ] Update frontend `.env.production.local`
- [ ] Generate secure `SECRET_KEY` (use `openssl rand -hex 32`)
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Set `COMPANYINFO_EMAIL` and `COMPANYINFO_PASSWORD`
- [ ] Configure `BACKEND_CORS_ORIGINS` (or let it auto-generate)
- [ ] Build frontend: `npm run build`
- [ ] Restart services
- [ ] Test all endpoints
- [ ] Test WebSocket connection
- [ ] Monitor logs for errors

---

## 🛠️ Troubleshooting

### Issue: CORS Errors

**Check CORS configuration:**
```bash
# Backend
cd backend
source venv/bin/activate
python -c "from app.core.config import settings; print(settings.cors_origins)"
```

**Manual override:**
```bash
# In .env
BACKEND_CORS_ORIGINS="https://your-domain.com,https://www.your-domain.com"
```

### Issue: WebSocket Connection Failed

**Check WebSocket URL:**
```bash
# Frontend console should show:
# "WebSocket: Connecting to wss://your-domain.com/api/v1/ws/updates?token=..."
```

**Verify Nginx WebSocket config:**
```bash
sudo nano /etc/nginx/sites-available/automation
# Ensure WebSocket location block is present
sudo nginx -t
sudo systemctl reload nginx
```

### Issue: API Not Found (404)

**Verify API URL:**
```bash
# Check frontend config
cat frontend/.env.production.local

# Should match backend domain
curl https://your-domain.com/api/v1/system/health
```

---

## 📞 Support

If you encounter issues:

1. **Check Logs:**
   ```bash
   sudo journalctl -u automation-backend -n 50
   sudo journalctl -u automation-celery -n 50
   ```

2. **Test Environment:**
   ```bash
   cd backend
   source venv/bin/activate
   python -c "from app.core.environment import EnvironmentConfig; EnvironmentConfig.print_environment_info()"
   ```

3. **Review Configuration:**
   - Backend: `cat .env`
   - Frontend: `cat frontend/.env.production.local`
   - Nginx: `sudo cat /etc/nginx/sites-available/automation`

---

## 🎉 Summary

The project now features:
- ✅ **Dynamic URL management** - No hardcoded URLs
- ✅ **Automatic environment detection** - Dev/staging/production
- ✅ **Flexible hosting** - Domain, IP, Docker, reverse proxy
- ✅ **SSL support** - Automatic https/wss detection
- ✅ **Easy deployment** - Single .env configuration
- ✅ **Production-ready** - Secure defaults and best practices

**Ready for Hostinger VPS deployment! 🚀**
