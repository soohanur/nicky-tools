# 📊 Monitoring & Maintenance Guide

## 🔍 Daily Monitoring Checklist

### Automated Health Check (Already Setup)

The monitoring script runs every 5 minutes via cron and checks:
- ✅ Service status (Backend API, Nginx)
- ✅ Disk space usage
- ✅ Memory usage
- ✅ CPU usage
- ✅ Chrome availability
- ✅ API responsiveness
- ✅ Recent automation runs
- ✅ Error rates in logs

**View monitoring logs:**
```bash
tail -f ~/automation_platform/automation_data/logs/monitor.log
```

---

## 📈 Key Metrics Dashboard

### Quick Status Check

```bash
# Run manual health check
~/automation_platform/deployment/monitor.sh

# Or create alias for easy access
echo "alias health='~/automation_platform/deployment/monitor.sh'" >> ~/.bashrc
source ~/.bashrc

# Now just run:
health
```

### Service Status

```bash
# Check all services
systemctl status automation-backend nginx

# Check specific service
systemctl status automation-backend

# View service logs
sudo journalctl -u automation-backend -f
```

### Real-Time Monitoring

```bash
# Watch system resources
htop

# Watch disk I/O
iotop

# Watch network
nethogs

# Watch processes
watch -n 1 'ps aux | grep python'
```

---

## 📊 Performance Metrics

### Daily Automation Stats

```bash
# Count processed companies today
TODAY=$(date +%Y-%m-%d)
grep "$TODAY" ~/automation_platform/automation_data/logs/automation.log | grep -c "Processing Row"

# Success rate
TOTAL=$(grep "$TODAY" ~/automation_platform/automation_data/logs/automation.log | grep -c "Processing Row")
SUCCESS=$(grep "$TODAY" ~/automation_platform/automation_data/logs/automation.log | grep -c "SUCCESS")
echo "Success rate: $(echo "scale=2; $SUCCESS * 100 / $TOTAL" | bc)%"

# Average processing time
# (Analyze log timestamps)
```

### API Statistics

```bash
# API request count (from nginx logs)
sudo tail -1000 /var/log/nginx/access.log | grep "/api/" | wc -l

# Most hit endpoints
sudo tail -1000 /var/log/nginx/access.log | grep "/api/" | awk '{print $7}' | sort | uniq -c | sort -rn

# Error rate
sudo tail -1000 /var/log/nginx/access.log | grep "/api/" | awk '{if ($9 >= 400) print $9}' | wc -l
```

### Database Performance (Phase 2+)

```sql
-- PostgreSQL query stats
SELECT 
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
ORDER BY n_tup_ins DESC;

-- Slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

---

## 🚨 Alert Configuration

### Email Alerts

**Setup:**
```bash
# Install mail utility
sudo apt install mailutils

# Configure email
echo "set smtp=smtp://smtp.gmail.com:587" >> ~/.mailrc
echo "set smtp-auth=login" >> ~/.mailrc
echo "set smtp-auth-user=your-email@gmail.com" >> ~/.mailrc
echo "set smtp-auth-password=your-app-password" >> ~/.mailrc
echo "set from=your-email@gmail.com" >> ~/.mailrc

# Test
echo "Test alert" | mail -s "Test Subject" your-email@gmail.com
```

**Update monitor.sh:**
```bash
nano ~/automation_platform/deployment/monitor.sh

# Set ALERT_EMAIL
ALERT_EMAIL="your-email@gmail.com"
```

### Slack Alerts (Recommended)

```bash
# Create Slack webhook
# Go to: https://api.slack.com/messaging/webhooks

# Add to monitor.sh
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

send_slack_alert() {
    local message="$1"
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"$message\"}" \
        "$SLACK_WEBHOOK"
}

# Use in alerts
send_slack_alert "⚠️ Disk usage at ${DISK_USAGE}%"
```

### SMS Alerts (Twilio)

```bash
# Install Twilio CLI
pip install twilio

# Create alert script
cat > ~/automation_platform/scripts/sms_alert.py << 'EOF'
from twilio.rest import Client

def send_sms(message):
    account_sid = 'YOUR_ACCOUNT_SID'
    auth_token = 'YOUR_AUTH_TOKEN'
    client = Client(account_sid, auth_token)
    
    message = client.messages.create(
        body=message,
        from_='+1234567890',
        to='+0987654321'
    )
    print(f"SMS sent: {message.sid}")

if __name__ == "__main__":
    import sys
    send_sms(sys.argv[1])
EOF

# Usage in monitor.sh
python3 ~/automation_platform/scripts/sms_alert.py "Critical: Disk full"
```

---

## 🔧 Maintenance Tasks

### Daily (Automated)

```bash
# Already setup in cron
# - Health checks (every 5 min)
# - Log rotation (daily)
# - Automation runs (2 AM)
```

### Weekly

```bash
# Review error logs
tail -500 ~/automation_platform/automation_data/logs/automation.log | grep ERROR

# Check disk usage trend
df -h /

# Review automation success rate
# (Create custom script)
```

### Monthly

```bash
# System updates
sudo apt update && sudo apt upgrade -y

# Chrome update
sudo apt install --only-upgrade google-chrome-stable

# Clean old logs (keep 30 days)
find ~/automation_platform/automation_data/logs -name "*.log" -mtime +30 -delete

# Clean old outputs (keep 60 days)
find ~/automation_platform/automation_data/output -name "DONE_*.csv" -mtime +60 -delete

# Backup important data
tar -czf backup_$(date +%Y%m%d).tar.gz ~/automation_platform/automation_data/output/

# Database vacuum (Phase 2+)
psql -c "VACUUM ANALYZE;"
```

---

## 📊 Custom Monitoring Dashboard

### Setup Grafana (Optional)

```bash
# Install Grafana
sudo apt install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt update
sudo apt install grafana

# Start Grafana
sudo systemctl enable grafana-server
sudo systemctl start grafana-server

# Access: http://your-vps-ip:3000
# Default: admin/admin
```

### Install Prometheus

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
sudo mv prometheus-* /opt/prometheus

# Create config
cat > /opt/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'automation'
    static_configs:
      - targets: ['localhost:8000']
EOF

# Create service
sudo tee /etc/systemd/system/prometheus.service > /dev/null << EOF
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
User=automation
ExecStart=/opt/prometheus/prometheus --config.file=/opt/prometheus/prometheus.yml
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable prometheus
sudo systemctl start prometheus
```

---

## 🐛 Troubleshooting Guide

### High Memory Usage

```bash
# Find memory hogs
ps aux --sort=-%mem | head -10

# Kill Chrome processes
pkill -f chrome

# Restart automation
sudo systemctl restart automation-backend
```

### High Disk Usage

```bash
# Find large files
du -h / | sort -rh | head -20

# Clean Docker (if using)
docker system prune -a

# Clean logs
sudo journalctl --vacuum-time=7d

# Clean package cache
sudo apt clean
```

### Chrome Crashes

```bash
# Check Chrome logs
cat ~/.config/google-chrome/chrome_debug.log

# Reinstall Chrome
sudo apt remove google-chrome-stable
sudo apt install ./google-chrome-stable_current_amd64.deb

# Clear Chrome cache
rm -rf ~/automation_platform/automation_data/chrome_profile/Default/Cache/*
```

### API Not Responding

```bash
# Check if port is in use
sudo netstat -tulpn | grep 8000

# Check service logs
sudo journalctl -u automation-backend -n 100

# Restart service
sudo systemctl restart automation-backend

# Test locally
curl -v http://localhost:8000/health
```

### Database Connection Errors (Phase 2+)

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Kill idle connections
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < now() - interval '30 minutes';"
```

---

## 📊 Log Analysis

### Extract Useful Metrics

```bash
# Today's automation runs
grep "$(date +%Y-%m-%d)" ~/automation_platform/automation_data/logs/automation.log | grep "Processing Row" | wc -l

# Error summary
grep "ERROR" ~/automation_platform/automation_data/logs/automation.log | tail -50

# Most common errors
grep "ERROR" ~/automation_platform/automation_data/logs/automation.log | awk -F'ERROR:' '{print $2}' | sort | uniq -c | sort -rn

# Processing time per company (custom parsing needed)
grep "completed successfully" ~/automation_platform/automation_data/logs/automation.log
```

### Log Rotation Configuration

```bash
# Check current config
cat /etc/logrotate.d/automation

# Modify if needed
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
    postrotate
        systemctl reload automation-backend > /dev/null 2>&1 || true
    endscript
}
```

---

## 🔐 Security Monitoring

### Failed Login Attempts

```bash
# Check SSH login attempts
sudo grep "Failed password" /var/log/auth.log | tail -20

# Block suspicious IPs
sudo fail2ban-client status sshd
```

### API Access Patterns

```bash
# Unusual API access
sudo tail -1000 /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn

# Block IP
sudo ufw deny from <ip-address>
```

### File Integrity

```bash
# Check for unauthorized changes
sudo debsums -c

# Monitor important files
sudo apt install aide
sudo aideinit
sudo aide --check
```

---

## 📈 Performance Optimization

### Chrome Memory Optimization

```bash
# Edit Chrome launch args in browser_automation.py
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-software-rasterizer')
chrome_options.add_argument('--max-old-space-size=512')
```

### Database Query Optimization (Phase 2+)

```sql
-- Add indexes
CREATE INDEX idx_company_name ON companies(name);
CREATE INDEX idx_created_at ON results(created_at);

-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM companies WHERE name = 'Test';
```

### Caching Strategy

```python
# Add Redis caching
import redis
r = redis.Redis(host='localhost', port=6379)

# Cache company info for 24h
def get_company_info(company_name):
    cached = r.get(f"company:{company_name}")
    if cached:
        return json.loads(cached)
    
    # Fetch from CompanyInfo
    data = search_company(company_name)
    r.setex(f"company:{company_name}", 86400, json.dumps(data))
    return data
```

---

## 🎯 SLA Monitoring

### Uptime Tracking

```bash
# Install uptime monitor
sudo apt install uptimed

# Check uptime history
uptime -p
uprecords
```

### SLA Metrics

**Target SLAs:**
- Uptime: 99.5% (Phase 1), 99.9% (Phase 3)
- API response time: <500ms
- Success rate: >95%
- Error resolution: <1 hour

**Calculate monthly uptime:**
```bash
# Total minutes in month
TOTAL_MINUTES=$((30 * 24 * 60))

# Downtime minutes
DOWNTIME=10

# Uptime percentage
UPTIME_PCT=$(echo "scale=4; (1 - $DOWNTIME / $TOTAL_MINUTES) * 100" | bc)
echo "Uptime: ${UPTIME_PCT}%"
```

---

## 📞 Incident Response

### Severity Levels

**Critical (P1):**
- System completely down
- Data loss
- Security breach

**Response:** Immediate (5 minutes)

**High (P2):**
- Service degraded
- High error rate (>20%)
- API unavailable

**Response:** 30 minutes

**Medium (P3):**
- Non-critical features broken
- Moderate error rate (5-20%)

**Response:** 4 hours

**Low (P4):**
- Minor issues
- Enhancement requests

**Response:** 1 business day

### Incident Checklist

1. **Detect**
   - Check monitoring alerts
   - Verify issue

2. **Respond**
   - Assess severity
   - Start timer
   - Notify team

3. **Mitigate**
   - Apply quick fix
   - Restore service

4. **Resolve**
   - Find root cause
   - Implement permanent fix
   - Verify fix

5. **Document**
   - Write post-mortem
   - Update runbooks
   - Improve monitoring

---

## 🔄 Backup & Recovery

### Automated Backups

```bash
# Add to crontab
0 3 * * * /home/automation/automation_platform/scripts/backup.sh

# Create backup script
cat > ~/automation_platform/scripts/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/home/automation/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup data
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" \
    ~/automation_platform/automation_data

# Backup code
tar -czf "$BACKUP_DIR/code_$DATE.tar.gz" \
    ~/automation_platform/automation_tool \
    ~/automation_platform/backend

# Database backup (Phase 2+)
pg_dump automation_db | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Keep last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x ~/automation_platform/scripts/backup.sh
```

### Disaster Recovery

```bash
# Test recovery
cd /tmp
mkdir recovery_test
cd recovery_test

# Extract backup
tar -xzf ~/backups/data_*.tar.gz
tar -xzf ~/backups/code_*.tar.gz

# Verify files
ls -la
```

---

**Version:** 1.0.0  
**Last Updated:** January 31, 2026  
**Status:** Production Ready
