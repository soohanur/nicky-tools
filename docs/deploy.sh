#!/bin/bash

################################################################################
# Project Deployment Script
# Deploys automation tool + backend API to VPS
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Automation Platform - Deployment Script                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
AUTOMATION_USER=$(whoami)
BASE_DIR="/home/$AUTOMATION_USER/automation_platform"
TOOL_DIR="$BASE_DIR/automation_tool"
BACKEND_DIR="$BASE_DIR/backend"

# Check if base directory exists
if [ ! -d "$BASE_DIR" ]; then
    echo -e "${RED}Error: Base directory not found. Run vps_setup.sh first.${NC}"
    exit 1
fi

echo -e "${GREEN}[1/8]${NC} Installing automation tool dependencies..."
cd "$TOOL_DIR"
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: requirements.txt not found in $TOOL_DIR${NC}"
    exit 1
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "  ✓ Dependencies installed"

echo -e "${GREEN}[2/8]${NC} Creating .env file if not exists..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "  ${YELLOW}⚠️  Please edit .env file with your configuration${NC}"
    else
        echo -e "  ${YELLOW}⚠️  No .env.example found. Create .env manually.${NC}"
    fi
else
    echo -e "  ✓ .env file exists"
fi

echo -e "${GREEN}[3/8]${NC} Setting up backend API..."
mkdir -p "$BACKEND_DIR"
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install fastapi uvicorn python-multipart
echo -e "  ✓ Backend dependencies installed"

# Create backend main.py if not exists
if [ ! -f "main.py" ]; then
    cat > main.py << 'EOF'
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import subprocess
import os
from pathlib import Path

app = FastAPI(title="Automation Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTOMATION_DIR = Path("/home/$USER/automation_platform/automation_tool")
DATA_DIR = Path("/home/$USER/automation_platform/automation_data")
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPT_PATH = Path("/home/$USER/automation_platform/scripts/run_automation.sh")

@app.get("/")
async def root():
    return {"message": "Automation Platform API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "chrome": os.path.exists("/usr/bin/google-chrome")}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    file_path = INPUT_DIR / file.filename
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"message": "File uploaded successfully", "filename": file.filename}

@app.post("/run-automation")
async def run_automation(background_tasks: BackgroundTasks):
    def run_script():
        subprocess.run([str(SCRIPT_PATH)], shell=True)
    background_tasks.add_task(run_script)
    return {"message": "Automation started in background"}

@app.get("/download-output/{filename}")
async def download_output(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return {"error": "File not found"}
    return FileResponse(file_path, media_type="text/csv", filename=filename)

@app.get("/list-outputs")
async def list_outputs():
    files = [f.name for f in OUTPUT_DIR.glob("DONE_*.csv")]
    return {"files": files}

@app.get("/logs")
async def get_logs(lines: int = 100):
    log_file = DATA_DIR / "logs" / "automation.log"
    if not log_file.exists():
        return {"logs": []}
    with open(log_file, "r") as f:
        log_lines = f.readlines()[-lines:]
    return {"logs": log_lines}
EOF
    # Replace $USER with actual username
    sed -i "s/\$USER/$AUTOMATION_USER/g" main.py
    echo -e "  ✓ Backend API created"
else
    echo -e "  ✓ Backend API already exists"
fi

echo -e "${GREEN}[4/8]${NC} Creating systemd services..."

# Backend service
sudo tee /etc/systemd/system/automation-backend.service > /dev/null << EOF
[Unit]
Description=Automation Platform Backend API
After=network.target

[Service]
Type=simple
User=$AUTOMATION_USER
WorkingDirectory=$BACKEND_DIR
ExecStart=$BACKEND_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo -e "  ✓ Backend service created"

echo -e "${GREEN}[5/8]${NC} Creating automation runner script..."
cat > "$BASE_DIR/scripts/run_automation.sh" << 'EOFSCRIPT'
#!/bin/bash

set -e

PROJECT_DIR="/home/$USER/automation_platform/automation_tool"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
LOG_FILE="/home/$USER/automation_platform/automation_data/logs/automation.log"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

log "Starting automation tool..."

if ! command -v google-chrome &> /dev/null; then
    error "Google Chrome not installed"
    exit 1
fi

log "✓ Chrome installed: $(google-chrome --version)"

cd "$PROJECT_DIR"

xvfb-run -a --server-args="-screen 0 1920x1080x24" \
    "$PYTHON" src/main.py 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    log "✓ Automation completed successfully"
else
    error "Automation failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
EOFSCRIPT

# Replace $USER with actual username
sed -i "s/\$USER/$AUTOMATION_USER/g" "$BASE_DIR/scripts/run_automation.sh"
chmod +x "$BASE_DIR/scripts/run_automation.sh"
echo -e "  ✓ Runner script created"

echo -e "${GREEN}[6/8]${NC} Configuring Nginx..."
sudo tee /etc/nginx/sites-available/automation > /dev/null << EOF
server {
    listen 80;
    server_name _;

    location / {
        return 200 'Automation Platform API\nAccess API at /api/';
        add_header Content-Type text/plain;
    }

    location /api {
        rewrite ^/api/(.*)$ /\$1 break;
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

sudo ln -sf /etc/nginx/sites-available/automation /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
echo -e "  ✓ Nginx configured"

echo -e "${GREEN}[7/8]${NC} Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable automation-backend.service
sudo systemctl start automation-backend.service
sleep 2

if systemctl is-active --quiet automation-backend; then
    echo -e "  ✓ Backend service running"
else
    echo -e "  ${RED}✗ Backend service failed to start${NC}"
    sudo journalctl -u automation-backend -n 20 --no-pager
fi

echo -e "${GREEN}[8/8]${NC} Setting up cron jobs..."
(crontab -l 2>/dev/null || echo "") | grep -v "run_automation.sh" | \
cat - <(echo "# Run automation daily at 2 AM") \
<(echo "0 2 * * * $BASE_DIR/scripts/run_automation.sh >> $BASE_DIR/automation_data/logs/cron.log 2>&1") | \
crontab -
echo -e "  ✓ Cron job added"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ Deployment Complete!                                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Service Status:${NC}"
systemctl is-active --quiet automation-backend && \
    echo -e "  Backend API: ${GREEN}✓ Running${NC} (http://localhost:8000)" || \
    echo -e "  Backend API: ${RED}✗ Stopped${NC}"
systemctl is-active --quiet nginx && \
    echo -e "  Nginx: ${GREEN}✓ Running${NC}" || \
    echo -e "  Nginx: ${RED}✗ Stopped${NC}"
echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo -e "  Test automation: ${BLUE}$BASE_DIR/scripts/run_automation.sh${NC}"
echo -e "  Check API: ${BLUE}curl http://localhost:8000/health${NC}"
echo -e "  View logs: ${BLUE}tail -f $BASE_DIR/automation_data/logs/automation.log${NC}"
echo -e "  Backend logs: ${BLUE}sudo journalctl -u automation-backend -f${NC}"
echo ""
