# 🏗️ Scalable Architecture Design

## 📐 System Architecture Evolution

### Phase 1: Single VPS (Current - Month 1-3)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hostinger VPS (2-4GB RAM)                     │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Application Layer                     │   │
│  │                                                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │   │
│  │  │  Frontend   │  │   Backend   │  │ Automation  │      │   │
│  │  │   (React)   │  │  (FastAPI)  │  │  (Selenium) │      │   │
│  │  │  Port 3000  │  │  Port 8000  │  │  Headless   │      │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Nginx (Port 80/443)                    │   │
│  │  - Reverse Proxy                                          │   │
│  │  - SSL Termination                                        │   │
│  │  - Static File Serving                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      File Storage                         │   │
│  │  - Input CSVs: /automation_data/input/                   │   │
│  │  - Output CSVs: /automation_data/output/                 │   │
│  │  - Logs: /automation_data/logs/                          │   │
│  │  - Chrome Profile: /automation_data/chrome_profile/      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

Performance:
- 100-500 companies/day
- Single Chrome instance
- Sequential processing
- Cost: $5-10/month
```

---

### Phase 2: Optimized VPS (Month 3-6)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hostinger VPS (4-8GB RAM)                     │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Application Layer                        │   │
│  │                                                            │   │
│  │  Frontend → Backend → Redis Queue → Workers (×3)         │   │
│  │                                                            │   │
│  │  Worker 1: Chrome Instance 1                             │   │
│  │  Worker 2: Chrome Instance 2                             │   │
│  │  Worker 3: Chrome Instance 3                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              PostgreSQL Database                          │   │
│  │  - Job queue                                              │   │
│  │  - Results cache                                          │   │
│  │  - User management                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

Performance:
- 1,000-2,000 companies/day
- 3 parallel Chrome instances
- Redis job queue
- PostgreSQL for persistence
- Cost: $15-25/month
```

---

### Phase 3: Multi-Server Architecture (Month 6-12)

```
                        ┌─────────────────┐
                        │  Load Balancer  │
                        │  (Nginx/HAProxy)│
                        └────────┬────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
        │   Frontend   │ │   Backend   │ │   Backend   │
        │   Server     │ │   Server 1  │ │   Server 2  │
        │  (Static)    │ │  (API)      │ │  (API)      │
        └──────────────┘ └──────┬──────┘ └──────┬──────┘
                                 │                │
                        ┌────────▼────────────────▼────────┐
                        │      Redis Cluster                │
                        │  (Job Queue + Cache)             │
                        └────────┬──────────────────────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
        │   Worker 1   │ │   Worker 2  │ │   Worker 3  │
        │   (VPS 1)    │ │   (VPS 2)   │ │   (VPS 3)   │
        │ 3×Chrome     │ │ 3×Chrome    │ │ 3×Chrome    │
        └──────────────┘ └─────────────┘ └─────────────┘
                                 │
                        ┌────────▼────────┐
                        │   PostgreSQL    │
                        │   (Master)      │
                        │                 │
                        │   Replica →     │
                        └─────────────────┘
                                 │
                        ┌────────▼────────┐
                        │   S3/Object     │
                        │   Storage       │
                        │  (CSV Files)    │
                        └─────────────────┘

Performance:
- 10,000+ companies/day
- 9+ parallel Chrome instances
- Distributed architecture
- High availability
- Auto-scaling
- Cost: $100-200/month
```

---

## 🔧 Technology Stack by Phase

### Phase 1 (Current)
```yaml
Infrastructure:
  - 1× Hostinger VPS (2-4GB RAM)
  
Backend:
  - FastAPI (REST API)
  - Python 3.11
  - Selenium WebDriver
  
Storage:
  - File system (CSV files)
  - Local logs
  
Web Server:
  - Nginx (reverse proxy)
  
Monitoring:
  - Cron logs
  - System logs
```

### Phase 2 (3-6 months)
```yaml
Infrastructure:
  - 1× Hostinger VPS (4-8GB RAM)
  
Backend:
  - FastAPI + Celery workers
  - Redis (job queue)
  - PostgreSQL (data storage)
  
Processing:
  - 3× parallel Chrome instances
  - Task queue with retries
  
Storage:
  - PostgreSQL (structured data)
  - File system (CSV files)
  
Monitoring:
  - Flower (Celery monitoring)
  - Custom dashboard
```

### Phase 3 (6-12 months)
```yaml
Infrastructure:
  - 1× Load Balancer
  - 2× API Servers
  - 3× Worker VPS (auto-scale)
  - 1× Database Server
  - S3-compatible storage
  
Backend:
  - FastAPI + Celery distributed
  - Redis Cluster
  - PostgreSQL with replication
  
Processing:
  - N× Chrome instances (elastic)
  - Priority queues
  - Failure recovery
  
Storage:
  - S3/Object Storage (files)
  - PostgreSQL (metadata)
  - Redis (cache)
  
Monitoring:
  - Prometheus + Grafana
  - Alerting (PagerDuty/Slack)
  - Distributed tracing
```

---

## 🚀 Migration Path

### Month 1-3: Foundation
**Objective:** Stable single-server operation

✅ Deploy to VPS  
✅ Automate daily runs  
✅ Monitor error rates  
✅ Collect performance metrics  
✅ Optimize Chrome memory usage  

**Success Metrics:**
- 95%+ success rate
- <30s per company
- 99% uptime

---

### Month 3-6: Optimization
**Objective:** Parallel processing

**Tasks:**
1. Install Redis
```bash
sudo apt install redis-server
```

2. Add Celery to requirements.txt
```python
celery==5.3.4
redis==5.0.1
flower==2.0.1
```

3. Convert to task queue
```python
# src/celery_app.py
from celery import Celery

app = Celery('automation', broker='redis://localhost:6379/0')

@app.task
def process_company(company_data):
    # Your existing logic
    pass
```

4. Deploy workers
```bash
celery -A src.celery_app worker --loglevel=info --concurrency=3
```

**Success Metrics:**
- 3× throughput increase
- 1,000+ companies/day
- <10s per company

---

### Month 6-12: Scale-Out
**Objective:** Distributed architecture

**Infrastructure Changes:**
1. **Load Balancer:**
   - Setup HAProxy or Nginx upstream
   - Health checks

2. **Database:**
   - Migrate to managed PostgreSQL
   - Setup replication

3. **Storage:**
   - Use S3-compatible storage (Backblaze B2, MinIO)
   - CDN for output files

4. **Monitoring:**
   - Prometheus for metrics
   - Grafana dashboards
   - Alerting

**Code Changes:**
```python
# Use database instead of CSV
from sqlalchemy import create_engine

engine = create_engine('postgresql://user:pass@db-server/automation')

# Store results in database
def save_result(result):
    with engine.connect() as conn:
        conn.execute(
            "INSERT INTO results VALUES (...)",
            result
        )
```

**Success Metrics:**
- 10,000+ companies/day
- 99.9% uptime
- Auto-scaling workers
- <5s per company

---

## 📊 Cost Analysis

### Phase 1 (Month 1-3)
```
Hostinger VPS 2:     $8.99/month
Domain (optional):   $2/month
Total:               ~$11/month

Processing capacity: 500 companies/day
Cost per company:    $0.0007
```

### Phase 2 (Month 3-6)
```
Hostinger VPS 4:     $18.99/month
Domain:              $2/month
Backup storage:      $2/month
Total:               ~$23/month

Processing capacity: 2,000 companies/day
Cost per company:    $0.00038
```

### Phase 3 (Month 6-12)
```
Load Balancer VPS:   $8.99/month
2× API Servers:      $17.98/month
3× Worker VPS:       $26.97/month
PostgreSQL (managed):$25/month
S3 Storage (1TB):    $5/month
Monitoring:          $0 (self-hosted)
Total:               ~$84/month

Processing capacity: 10,000+ companies/day
Cost per company:    $0.00028
```

---

## 🔐 Security Layers

### Phase 1
- ✅ SSH key authentication
- ✅ Firewall (UFW)
- ✅ SSL certificate
- ✅ Regular updates
- ✅ Backup automation

### Phase 2
- ✅ All Phase 1 features
- ✅ API authentication (JWT)
- ✅ Rate limiting
- ✅ Database encryption
- ✅ Secrets management (Vault)

### Phase 3
- ✅ All Phase 2 features
- ✅ WAF (Web Application Firewall)
- ✅ DDoS protection
- ✅ Intrusion detection
- ✅ Audit logging
- ✅ Compliance (GDPR, SOC 2)

---

## 📈 Performance Benchmarks

### Single VPS (Phase 1)
```
Companies/hour:     20-50
Companies/day:      500
Success rate:       95%
Avg time/company:   30s
Memory usage:       800MB
CPU usage:          40%
```

### Optimized VPS (Phase 2)
```
Companies/hour:     80-100
Companies/day:      2,000
Success rate:       97%
Avg time/company:   10s
Memory usage:       2.5GB
CPU usage:          70%
Workers:            3 parallel
```

### Distributed (Phase 3)
```
Companies/hour:     400-500
Companies/day:      10,000+
Success rate:       98%
Avg time/company:   5s
Total memory:       12GB (across workers)
Total CPU:          Multiple cores
Workers:            9+ parallel (auto-scale)
```

---

## 🎯 Implementation Roadmap

### Week 1-2: Deploy Phase 1
- [ ] Setup VPS
- [ ] Deploy automation tool
- [ ] Configure cron jobs
- [ ] Test end-to-end
- [ ] Monitor for 1 week

### Week 3-4: Stabilization
- [ ] Fix any bugs
- [ ] Optimize Chrome settings
- [ ] Improve error handling
- [ ] Setup backup system
- [ ] Document processes

### Month 2-3: Optimization
- [ ] Analyze bottlenecks
- [ ] Optimize SQL queries (if using DB)
- [ ] Reduce memory usage
- [ ] Improve success rate to 98%+
- [ ] Add retry logic

### Month 3-4: Prepare Phase 2
- [ ] Design queue architecture
- [ ] Test Redis locally
- [ ] Refactor code for Celery
- [ ] Create migration plan
- [ ] Upgrade VPS

### Month 4-6: Deploy Phase 2
- [ ] Install Redis & PostgreSQL
- [ ] Deploy Celery workers
- [ ] Migrate data
- [ ] Test parallel processing
- [ ] Monitor performance

### Month 6+: Plan Phase 3
- [ ] Evaluate scaling needs
- [ ] Design distributed architecture
- [ ] Cost analysis
- [ ] Vendor selection
- [ ] Gradual migration

---

## 🔄 Disaster Recovery

### Backup Strategy
```bash
# Daily backup script
#!/bin/bash

BACKUP_DIR="/home/automation/backups"
DATE=$(date +%Y%m%d)

# Backup data
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" \
    /home/automation/automation_platform/automation_data

# Backup database (Phase 2+)
pg_dump automation_db > "$BACKUP_DIR/db_$DATE.sql"

# Keep last 30 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

### Recovery Procedures
```bash
# 1. Restore data
tar -xzf backup.tar.gz -C /home/automation/automation_platform/

# 2. Restore database
psql automation_db < backup.sql

# 3. Restart services
sudo systemctl restart automation-backend
```

---

## 📞 Decision Matrix

**Choose Phase 1 if:**
- ✅ Processing < 500 companies/day
- ✅ Budget < $15/month
- ✅ Single user/admin
- ✅ Learning/testing phase

**Choose Phase 2 if:**
- ✅ Processing 500-2,000 companies/day
- ✅ Budget $20-30/month
- ✅ Need faster processing
- ✅ Multiple concurrent jobs

**Choose Phase 3 if:**
- ✅ Processing 10,000+ companies/day
- ✅ Budget $80-200/month
- ✅ Need 99.9% uptime
- ✅ Multiple users/customers
- ✅ API rate limits exceeded

---

**Current Recommendation:** Start with Phase 1, monitor metrics, scale when needed.

**Version:** 1.0.0  
**Last Updated:** January 31, 2026
