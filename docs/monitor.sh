#!/bin/bash

################################################################################
# Monitoring & Health Check Script
# Monitors all services and sends alerts
################################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BASE_DIR="/home/$(whoami)/automation_platform"
LOG_FILE="$BASE_DIR/automation_data/logs/monitor.log"
ALERT_EMAIL=""  # Set your email for alerts

# Thresholds
DISK_WARNING=80
DISK_CRITICAL=90
MEMORY_WARNING=80
CPU_WARNING=80

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local subject="$1"
    local message="$2"
    
    if [ ! -z "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    fi
}

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   System Health Check                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# 1. Check services
log "Checking services..."

if systemctl is-active --quiet automation-backend; then
    log "  ✓ Backend API: Running"
else
    error "  ✗ Backend API: Stopped"
    send_alert "Alert: Backend API Down" "The automation backend API is not running."
    sudo systemctl start automation-backend
fi

if systemctl is-active --quiet nginx; then
    log "  ✓ Nginx: Running"
else
    error "  ✗ Nginx: Stopped"
    send_alert "Alert: Nginx Down" "Nginx web server is not running."
    sudo systemctl start nginx
fi

# 2. Check disk space
log "Checking disk space..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

if [ $DISK_USAGE -ge $DISK_CRITICAL ]; then
    error "  ✗ Disk usage CRITICAL: ${DISK_USAGE}%"
    send_alert "Alert: Disk Space Critical" "Disk usage is at ${DISK_USAGE}%"
elif [ $DISK_USAGE -ge $DISK_WARNING ]; then
    warn "  ⚠ Disk usage WARNING: ${DISK_USAGE}%"
else
    log "  ✓ Disk usage OK: ${DISK_USAGE}%"
fi

# 3. Check memory
log "Checking memory..."
MEMORY_USAGE=$(free | awk '/Mem:/ {printf("%d", $3/$2 * 100)}')

if [ $MEMORY_USAGE -ge $MEMORY_WARNING ]; then
    warn "  ⚠ Memory usage: ${MEMORY_USAGE}%"
else
    log "  ✓ Memory usage OK: ${MEMORY_USAGE}%"
fi

# 4. Check CPU
log "Checking CPU..."
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 | cut -d'.' -f1)

if [ $CPU_USAGE -ge $CPU_WARNING ]; then
    warn "  ⚠ CPU usage: ${CPU_USAGE}%"
else
    log "  ✓ CPU usage OK: ${CPU_USAGE}%"
fi

# 5. Check Chrome
log "Checking Chrome..."
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    log "  ✓ Chrome installed: $CHROME_VERSION"
else
    error "  ✗ Chrome not found"
    send_alert "Alert: Chrome Missing" "Google Chrome is not installed on the server."
fi

# 6. Check API health
log "Checking API endpoint..."
if curl -sf http://localhost:8000/health > /dev/null; then
    log "  ✓ API responding"
else
    error "  ✗ API not responding"
    send_alert "Alert: API Not Responding" "The API health endpoint is not responding."
fi

# 7. Check recent automation runs
log "Checking recent automation runs..."
LAST_RUN=$(find "$BASE_DIR/automation_data/output" -name "DONE_*.csv" -mtime -1 | wc -l)

if [ $LAST_RUN -gt 0 ]; then
    log "  ✓ Automation ran in last 24h ($LAST_RUN outputs)"
else
    warn "  ⚠ No automation outputs in last 24h"
fi

# 8. Check error rate in logs
log "Checking error rate..."
if [ -f "$BASE_DIR/automation_data/logs/automation.log" ]; then
    ERROR_COUNT=$(tail -1000 "$BASE_DIR/automation_data/logs/automation.log" | grep -c "ERROR" || true)
    log "  Recent errors in last 1000 log lines: $ERROR_COUNT"
    
    if [ $ERROR_COUNT -gt 50 ]; then
        warn "  ⚠ High error rate detected: $ERROR_COUNT errors"
        send_alert "Alert: High Error Rate" "Detected $ERROR_COUNT errors in recent logs."
    fi
fi

# 9. Check file counts
log "Checking file counts..."
INPUT_COUNT=$(ls -1 "$BASE_DIR/automation_data/input" | wc -l)
OUTPUT_COUNT=$(ls -1 "$BASE_DIR/automation_data/output" | wc -l)

log "  Input files: $INPUT_COUNT"
log "  Output files: $OUTPUT_COUNT"

# 10. System uptime
log "System uptime: $(uptime -p)"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Health Check Complete                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""

# Summary
echo -e "${BLUE}Summary:${NC}"
echo -e "  Disk: ${DISK_USAGE}%"
echo -e "  Memory: ${MEMORY_USAGE}%"
echo -e "  CPU: ${CPU_USAGE}%"
echo -e "  Services: $(systemctl is-active automation-backend nginx | grep -c active)/2 active"
echo ""
