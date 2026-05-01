#!/bin/bash
################################################################################
# Deployment Script for Automation Platform
# Run this script after vps_setup.sh and transferring project files
################################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

echo "=================================="
echo "🚀 Deployment Script"
echo "=================================="
echo ""

# Get project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

print_info "Project directory: $PROJECT_DIR"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found!"
    if [ -f ".env.production" ]; then
        print_info "Copying .env.production to .env"
        cp .env.production .env
        print_error "⚠️  IMPORTANT: Edit .env file and update:"
        echo "   - DOMAIN_NAME"
        echo "   - SECRET_KEY"
        echo "   - POSTGRES_PASSWORD"
        echo "   - COMPANYINFO_EMAIL"
        echo "   - COMPANYINFO_PASSWORD"
        echo ""
        read -p "Press Enter after editing .env file..."
    else
        print_error ".env.production not found. Please create .env file first."
        exit 1
    fi
fi

# Load environment variables
source .env

# Validate required variables
print_info "Validating environment variables..."
REQUIRED_VARS=("DOMAIN_NAME" "SECRET_KEY" "POSTGRES_PASSWORD" "COMPANYINFO_EMAIL" "COMPANYINFO_PASSWORD")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        print_error "Required variable $var is not set in .env"
        exit 1
    fi
done
print_success "Environment variables validated"

# Setup PostgreSQL database
print_info "Step 1/8: Setting up PostgreSQL database..."
sudo -u postgres psql <<EOF
-- Drop database if exists (for fresh install)
DROP DATABASE IF EXISTS ${POSTGRES_DB};
CREATE DATABASE ${POSTGRES_DB};

-- Drop user if exists
DROP USER IF EXISTS ${POSTGRES_USER};
CREATE USER ${POSTGRES_USER} WITH ENCRYPTED PASSWORD '${POSTGRES_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};

-- Grant schema permissions
\c ${POSTGRES_DB}
GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};
EOF
print_success "Database created: ${POSTGRES_DB}"

# Install backend dependencies
print_info "Step 2/8: Installing backend dependencies..."
cd "$PROJECT_DIR/backend"

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
print_success "Backend dependencies installed"

# Run database migrations
print_info "Step 3/8: Running database migrations..."
alembic upgrade head
print_success "Database migrations completed"

# Create necessary directories
print_info "Step 4/8: Creating directories..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/automation_data"
mkdir -p "$PROJECT_DIR/chrome_profiles"
mkdir -p "$PROJECT_DIR/scraply/csv_files/input"
mkdir -p "$PROJECT_DIR/scraply/csv_files/output"
chmod -R 755 "$PROJECT_DIR/logs"
chmod -R 755 "$PROJECT_DIR/automation_data"
print_success "Directories created"

# Install frontend dependencies and build
print_info "Step 5/8: Building frontend..."
cd "$PROJECT_DIR/frontend"

# Create frontend .env file
if [ ! -f ".env.production.local" ]; then
    cp .env.production .env.production.local
    # Update with domain from backend .env
    sed -i "s|https://your-domain.com|https://${DOMAIN_NAME}|g" .env.production.local
fi

npm install
npm run build
print_success "Frontend built successfully"

# Setup systemd services
print_info "Step 6/8: Creating systemd services..."

# Backend service
sudo tee /etc/systemd/system/automation-backend.service > /dev/null <<EOF
[Unit]
Description=Automation Platform Backend API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery service
sudo tee /etc/systemd/system/automation-celery.service > /dev/null <<EOF
[Unit]
Description=Automation Platform Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/backend/venv/bin/celery -A app.core.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd services created"

# Configure Nginx
print_info "Step 7/8: Configuring Nginx..."

sudo tee /etc/nginx/sites-available/automation > /dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    client_max_body_size 100M;
    proxy_connect_timeout 600;
    proxy_send_timeout 600;
    proxy_read_timeout 600;
    send_timeout 600;

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # WebSocket
    location /api/v1/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    # API Docs
    location ~ ^/(docs|redoc|openapi.json) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
    }

    # Frontend
    location / {
        root $PROJECT_DIR/frontend/dist;
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        root $PROJECT_DIR/frontend/dist;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/automation /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
sudo nginx -t
sudo systemctl reload nginx
print_success "Nginx configured"

# Start services
print_info "Step 8/8: Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable automation-backend automation-celery
sudo systemctl restart automation-backend
sudo systemctl restart automation-celery

# Wait for services to start
sleep 3

# Check service status
if systemctl is-active --quiet automation-backend; then
    print_success "Backend service started"
else
    print_error "Backend service failed to start"
    sudo journalctl -u automation-backend -n 20
fi

if systemctl is-active --quiet automation-celery; then
    print_success "Celery service started"
else
    print_error "Celery service failed to start"
    sudo journalctl -u automation-celery -n 20
fi

echo ""
print_success "✨ Deployment completed!"
echo ""

# Print access information
echo "=================================="
echo "📋 Access Information"
echo "=================================="
echo "Frontend:  http://${DOMAIN_NAME}"
echo "API Docs:  http://${DOMAIN_NAME}/docs"
echo "API:       http://${DOMAIN_NAME}/api/v1"
echo ""

# SSL setup prompt
echo "=================================="
echo "🔒 SSL Setup (Optional)"
echo "=================================="
echo "To enable HTTPS, run:"
echo "sudo certbot --nginx -d ${DOMAIN_NAME}"
echo ""
echo "After SSL setup:"
echo "1. Update .env: USE_HTTPS=True"
echo "2. Update frontend/.env.production.local: VITE_API_BASE_URL=https://${DOMAIN_NAME}"
echo "3. Rebuild frontend: cd frontend && npm run build"
echo "4. Restart services: sudo systemctl restart automation-backend"
echo ""

# Print monitoring commands
echo "=================================="
echo "📊 Monitoring Commands"
echo "=================================="
echo "Check services:"
echo "  sudo systemctl status automation-backend"
echo "  sudo systemctl status automation-celery"
echo ""
echo "View logs:"
echo "  sudo journalctl -u automation-backend -f"
echo "  sudo journalctl -u automation-celery -f"
echo ""
echo "Restart services:"
echo "  sudo systemctl restart automation-backend"
echo "  sudo systemctl restart automation-celery"
echo ""
echo "=================================="
