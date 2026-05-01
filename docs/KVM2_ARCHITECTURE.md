# 🏗️ System Architecture for Hostinger KVM 2

## 📋 Your Server Specifications

```yaml
Plan: Hostinger KVM 2
vCPU: 2 cores
RAM: 8 GB
Storage: 100 GB NVMe
Bandwidth: 8 TB/month
OS: Ubuntu 22.04 LTS
Cost: $6.99/mo (promo) → $12.99/mo (regular)
```

---

## 🎯 Optimized Architecture for KVM 2

### **Complete System Layout**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Hostinger KVM 2 VPS Server                        │
│                    2 vCPU | 8GB RAM | 100GB NVMe                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Port 80/443 (External)                       │ │
│  │                           ▼                                     │ │
│  │  ╔══════════════════════════════════════════════════════════╗  │ │
│  │  ║                  NGINX (Reverse Proxy)                    ║  │ │
│  │  ║  - SSL Termination (Let's Encrypt)                       ║  │ │
│  │  ║  - Load Balancing                                        ║  │ │
│  │  ║  - Static File Serving                                   ║  │ │
│  │  ║  - Request Routing                                       ║  │ │
│  │  ║  RAM: ~50 MB | CPU: 2-5%                                ║  │ │
│  │  ╚══════════════════════════════════════════════════════════╝  │ │
│  │                           ▼                                     │ │
│  │           ┌──────────────┴──────────────┐                      │ │
│  │           ▼                             ▼                      │ │
│  │  ┌─────────────────┐          ┌────────────────────┐          │ │
│  │  │   Frontend      │          │   Backend API      │          │ │
│  │  │   (React)       │          │   (FastAPI)        │          │ │
│  │  │   Port 3000     │          │   Port 8000        │          │ │
│  │  │                 │          │                    │          │ │
│  │  │ - Dashboard     │          │ - REST API         │          │ │
│  │  │ - File Upload   │          │ - Auth             │          │ │
│  │  │ - Results View  │          │ - Job Queue        │          │ │
│  │  │                 │          │ - File Management  │          │ │
│  │  │ RAM: ~100 MB    │          │ RAM: ~300 MB       │          │ │
│  │  │ CPU: 5%         │          │ CPU: 10-15%        │          │ │
│  │  └─────────────────┘          └────────┬───────────┘          │ │
│  │                                         │                      │ │
│  │                                         ▼                      │ │
│  │                         ┌───────────────────────────┐          │ │
│  │                         │  Automation Engine        │          │ │
│  │                         │  (Python + Selenium)      │          │ │
│  │                         │                           │          │ │
│  │                         │  ┌─────────────────────┐ │          │ │
│  │                         │  │  Chrome Instance 1  │ │          │ │
│  │                         │  │  (Headless)         │ │          │ │
│  │                         │  │  RAM: ~800 MB       │ │          │ │
│  │                         │  │  CPU: 30-40%        │ │          │ │
│  │                         │  └─────────────────────┘ │          │ │
│  │                         │                           │          │ │
│  │                         │  ┌─────────────────────┐ │          │ │
│  │                         │  │  Chrome Instance 2  │ │          │ │
│  │                         │  │  (Optional/Phase 2) │ │          │ │
│  │                         │  │  RAM: ~800 MB       │ │          │ │
│  │                         │  │  CPU: 30-40%        │ │          │ │
│  │                         │  └─────────────────────┘ │          │ │
│  │                         │                           │          │ │
│  │                         │  Total RAM: 800-1600 MB  │          │ │
│  │                         │  Total CPU: 30-80%       │          │ │
│  │                         └───────────┬───────────────┘          │ │
│  │                                     │                          │ │
│  └─────────────────────────────────────┼──────────────────────────┘ │
│                                        │                            │
│  ┌─────────────────────────────────────▼──────────────────────────┐ │
│  │                    Storage Layer (100 GB NVMe)                  │ │
│  │                                                                 │ │
│  │  /home/automation/automation_platform/                         │ │
│  │  ├── automation_tool/          [Application Code: 2 GB]        │ │
│  │  ├── backend/                  [API Code: 500 MB]              │ │
│  │  ├── frontend/                 [React Build: 200 MB]           │ │
│  │  └── automation_data/                                          │ │
│  │      ├── input/                [CSV Files: 5 GB]               │ │
│  │      ├── output/               [Results: 15 GB]                │ │
│  │      ├── logs/                 [Log Files: 2 GB]               │ │
│  │      └── chrome_profile/       [Browser Data: 2 GB]            │ │
│  │                                                                 │ │
│  │  System & OS:                  [Ubuntu 22.04: 5 GB]            │ │
│  │  Swap:                         [2 GB]                          │ │
│  │  Free Space:                   [~65 GB available]              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    Process Management                            │ │
│  │                                                                  │ │
│  │  Systemd Services:                                              │ │
│  │  - automation-backend.service    [Backend API]                 │ │
│  │  - nginx.service                 [Web Server]                  │ │
│  │                                                                  │ │
│  │  Cron Jobs:                                                     │ │
│  │  - Daily automation (2 AM)                                     │ │
│  │  - Health checks (every 5 min)                                 │ │
│  │  - Log cleanup (weekly)                                        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    Resource Allocation                           │ │
│  │                                                                  │ │
│  │  CPU Usage (2 vCPU cores):                                      │ │
│  │  ████████████████████░░░░░░░░░░░░ 60-80% peak                  │ │
│  │  - Chrome: 30-40% per instance                                 │ │
│  │  - Backend: 10-15%                                             │ │
│  │  - Nginx: 2-5%                                                 │ │
│  │  - System: 10-15%                                              │ │
│  │  - Reserve: 20-40% for bursts                                  │ │
│  │                                                                  │ │
│  │  RAM Usage (8 GB total):                                        │ │
│  │  ████████████████░░░░░░░░░░░░░░░░ 4-5 GB used                  │ │
│  │  - Chrome: 800 MB × workers                                    │ │
│  │  - Backend: 300 MB                                             │ │
│  │  - Frontend: 100 MB                                            │ │
│  │  - Nginx: 50 MB                                                │ │
│  │  - System: 800 MB                                              │ │
│  │  - Buffers/Cache: 1.5 GB                                       │ │
│  │  - Free: 2-3 GB                                                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

                              ▼
                    ┌──────────────────┐
                    │   External User  │
                    │  - Upload CSV    │
                    │  - View Results  │
                    │  - Monitor Logs  │
                    └──────────────────┘
```

---

## 🔄 Complete Workflow Diagram

### **End-to-End Processing Flow**

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW OVERVIEW                            │
└─────────────────────────────────────────────────────────────────────┘

1. USER UPLOADS CSV
   │
   ▼
┌──────────────────┐
│  Web Browser     │ ──→ HTTPS ──→ Nginx (Port 443)
│  or API Client   │              │
└──────────────────┘              ▼
                           ┌─────────────────┐
                           │  Backend API    │
                           │  POST /upload   │
                           └────────┬────────┘
                                    │
                                    ▼
                           ┌─────────────────────────┐
                           │  Save to Input Folder   │
                           │  /automation_data/input/│
                           └────────┬────────────────┘
                                    │
                                    ▼
2. TRIGGER AUTOMATION (Manual or Cron)
   │
   ▼
┌──────────────────────────────────────────┐
│  POST /api/run-automation                │
│  OR                                      │
│  Cron Job: 0 2 * * *                   │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│  Execute: run_automation.sh              │
│  - Check Chrome availability             │
│  - Activate Python venv                  │
│  - Start xvfb (virtual display)         │
│  - Launch main.py                        │
└────────────┬─────────────────────────────┘
             │
             ▼
3. PROCESSING PIPELINE
   │
   ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 0: Read CSV                                               │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Excel Reader Module                                    │    │
│  │  - Open input CSV file                                  │    │
│  │  - Parse columns: CB, CC, CD, CF                       │    │
│  │  - Extract company name + address                       │    │
│  │  - Create processing queue                              │    │
│  │  - Return list of companies                             │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  FOR EACH COMPANY (Sequential Processing)                       │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Row: "ABC Company, 123 Main St, Amsterdam"            │    │
│  └────────────────────────────────────────────────────────┘    │
│                         │                                        │
│                         ▼                                        │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  STEP 1: Initialize Chrome                                │ │
│  │  - Launch Chrome in headless mode                         │ │
│  │  - Load existing profile (if available)                   │ │
│  │  - Check login status                                     │ │
│  │  - Auto-login if needed                                   │ │
│  │  RAM: ~800 MB | Time: ~3s                                │ │
│  └───────────────────┬───────────────────────────────────────┘ │
│                      │                                          │
│                      ▼                                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  STEP 2: Search by Company Name                          │ │
│  │  - Navigate to CompanyInfo.com                           │ │
│  │  - Find search input field                               │ │
│  │  - Enter: "ABC Company"                                  │ │
│  │  - Submit search                                         │ │
│  │  - Wait for results                                      │ │
│  │  Time: ~5s                                               │ │
│  └───────────────────┬───────────────────────────────────────┘ │
│                      │                                          │
│                      ▼                                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  STEP 3: Evaluate Results                                │ │
│  │                                                           │ │
│  │  ┌─────────────────┐     ┌─────────────────┐           │ │
│  │  │ Exactly 1 match │ YES │ Click result    │ ──┐       │ │
│  │  └────────┬────────┘     └─────────────────┘   │       │ │
│  │           │ NO                                  │       │ │
│  │           ▼                                     │       │ │
│  │  ┌─────────────────┐                           │       │ │
│  │  │ Multiple/None   │                           │       │ │
│  │  └────────┬────────┘                           │       │ │
│  │           │                                     │       │ │
│  │           ▼                                     │       │ │
│  │  ┌─────────────────────────────────────┐       │       │ │
│  │  │ STEP 4: Search by Address          │       │       │ │
│  │  │ - Clear search                      │       │       │ │
│  │  │ - Enter: "123 Main St Amsterdam"   │       │       │ │
│  │  │ - Submit search                     │       │       │ │
│  │  │ - Check results                     │       │       │ │
│  │  │ Time: ~5s                           │       │       │ │
│  │  └────────┬────────────────────────────┘       │       │ │
│  │           │                                     │       │ │
│  │           ▼                                     │       │ │
│  │  ┌─────────────────┐                           │       │ │
│  │  │ Found match?    │ YES ────────────────────────┘     │ │
│  │  └────────┬────────┘                                   │ │
│  │           │ NO                                         │ │
│  │           ▼                                            │ │
│  │  ┌────────────────┐                                   │ │
│  │  │ Mark as FAILED │                                   │ │
│  │  │ Move to next   │                                   │ │
│  │  └────────────────┘                                   │ │
│  └────────────────────────────┬────────────────────────────┘ │
│                               │                               │
│                               ▼                               │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  STEP 5: Extract Contact Information                     │ │
│  │  - Parse company page HTML                               │ │
│  │  - Find phone numbers (prefer 06, fallback 05)          │ │
│  │  - Extract email addresses                               │ │
│  │  - Get business name                                     │ │
│  │  - Get owner name                                        │ │
│  │  - Normalize formats                                     │ │
│  │  Time: ~2s                                               │ │
│  └───────────────────┬───────────────────────────────────────┘ │
│                      │                                          │
│                      ▼                                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  STEP 6: Save Results                                     │ │
│  │  - Write to output CSV immediately                        │ │
│  │  - Update columns: CG (phone), CH (email)                │ │
│  │  - Format: DONE_[original_filename].csv                  │ │
│  │  - Log success/failure                                    │ │
│  │  Time: <1s                                                │ │
│  └───────────────────┬───────────────────────────────────────┘ │
│                      │                                          │
│                      ▼                                          │
│           ┌──────────────────┐                                 │
│           │  Next Company?   │                                 │
│           └────────┬─────────┘                                 │
│                    │                                            │
│                    │ YES → Loop back to top                     │
│                    │                                            │
│                    │ NO                                         │
│                    ▼                                            │
└────────────────────────────────────────────────────────────────┘
                     │
                     ▼
4. COMPLETION
   │
   ▼
┌──────────────────────────────────────────┐
│  Generate Summary Report                  │
│  - Total processed: 150                  │
│  - Successful: 142                       │
│  - Failed: 8                             │
│  - Success rate: 94.7%                   │
│  - Output file: DONE_input.csv          │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────┐
│  Cleanup                                  │
│  - Close Chrome browser                   │
│  - Clear memory                           │
│  - Rotate logs                            │
│  - Update statistics                      │
└────────────┬─────────────────────────────┘
             │
             ▼
5. USER DOWNLOADS RESULTS
   │
   ▼
┌──────────────────┐
│  Web Browser     │ ←─ HTTPS ←─ Nginx ←─ Backend API
│  GET /download   │              │
└──────────────────┘              ▼
                           ┌─────────────────────────┐
                           │  Serve Output CSV       │
                           │  /automation_data/output│
                           └─────────────────────────┘
```

---

## ⚙️ Resource Optimization for KVM 2

### **Configuration Profiles**

#### **Profile 1: Conservative (Default - Start Here)**
```bash
# .env configuration
MAX_WORKERS=1
HEADLESS_MODE=True
IMPLICIT_WAIT=5
PAGE_LOAD_TIMEOUT=30
COMPANYINFO_SEARCH_TIMEOUT=10

# Expected Performance
Companies/day: 500-800
RAM usage: 2.5 GB (31%)
CPU usage: 50-60%
Success rate: 95%+
Avg time/company: 25-30s
```

#### **Profile 2: Balanced (After 1 Week Testing)**
```bash
# .env configuration
MAX_WORKERS=1
HEADLESS_MODE=True
IMPLICIT_WAIT=3
PAGE_LOAD_TIMEOUT=20
COMPANYINFO_SEARCH_TIMEOUT=7

# Expected Performance
Companies/day: 800-1200
RAM usage: 2.8 GB (35%)
CPU usage: 60-70%
Success rate: 95%+
Avg time/company: 18-22s
```

#### **Profile 3: Aggressive (Month 2+, Tested)**
```bash
# .env configuration
MAX_WORKERS=2
HEADLESS_MODE=True
IMPLICIT_WAIT=2
PAGE_LOAD_TIMEOUT=15
COMPANYINFO_SEARCH_TIMEOUT=5

# Expected Performance
Companies/day: 1500-2000
RAM usage: 4.5 GB (56%)
CPU usage: 75-85%
Success rate: 94%+
Avg time/company: 12-15s
```

#### **Profile 4: Maximum (Phase 2, With Redis)**
```bash
# .env configuration
MAX_WORKERS=3
HEADLESS_MODE=True
IMPLICIT_WAIT=2
PAGE_LOAD_TIMEOUT=10
COMPANYINFO_SEARCH_TIMEOUT=5

# Additional Services
- Redis (caching): 200 MB
- PostgreSQL (queue): 500 MB

# Expected Performance
Companies/day: 2000-3000
RAM usage: 6.5 GB (81%)
CPU usage: 90-95%
Success rate: 93%+
Avg time/company: 8-10s
```

---

## 📊 Performance Benchmarks on KVM 2

### **Real-World Processing Times**

```
┌─────────────────────────────────────────────────────────────┐
│  Processing 100 Companies - Timeline                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Conservative (1 worker):                                   │
│  ████████████████████████████████ 40-50 minutes            │
│  - Setup: 30s                                               │
│  - Per company: 25s avg                                     │
│  - Total: ~42 minutes                                       │
│                                                              │
│  Balanced (1 worker optimized):                             │
│  ████████████████████ 30-35 minutes                        │
│  - Setup: 25s                                               │
│  - Per company: 18s avg                                     │
│  - Total: ~31 minutes                                       │
│                                                              │
│  Aggressive (2 workers):                                    │
│  ████████████ 18-22 minutes                                │
│  - Setup: 35s (2 browsers)                                  │
│  - Per company: 12s avg (parallel)                          │
│  - Total: ~20 minutes                                       │
│                                                              │
│  Maximum (3 workers):                                       │
│  ████████ 12-15 minutes                                    │
│  - Setup: 45s (3 browsers)                                  │
│  - Per company: 8s avg (parallel)                           │
│  - Total: ~14 minutes                                       │
└─────────────────────────────────────────────────────────────┘
```

### **Daily Capacity Calculations**

```
If running 24/7 continuously:

Conservative (1 worker × 25s):
- Companies/hour: 144
- Companies/day: 3,456
- Realistic (with breaks): 2,000/day

Balanced (1 worker × 18s):
- Companies/hour: 200
- Companies/day: 4,800
- Realistic (with breaks): 3,000/day

Aggressive (2 workers × 12s):
- Companies/hour: 300
- Companies/day: 7,200
- Realistic (with breaks): 5,000/day

Maximum (3 workers × 8s):
- Companies/hour: 450
- Companies/day: 10,800
- Realistic (with breaks): 7,000/day
```

---

## 🎯 Recommended Deployment Strategy

### **Phase 1: Initial Deployment (Week 1-2)**

```bash
1. Start Conservative
   - MAX_WORKERS=1
   - Monitor RAM: should be ~2.5 GB
   - Monitor CPU: should be ~50-60%
   - Target: 500 companies/day

2. Collect Metrics
   - Success rate
   - Average processing time
   - Error patterns
   - Peak resource usage

3. Optimize Settings
   - Reduce timeouts gradually
   - Monitor impact on success rate
   - Adjust based on CompanyInfo response times
```

### **Phase 2: Optimization (Week 3-4)**

```bash
1. Switch to Balanced Profile
   - Reduce IMPLICIT_WAIT from 5 to 3
   - Monitor success rate (must stay >95%)
   - Target: 1,000 companies/day

2. Fine-tune Error Handling
   - Analyze failed searches
   - Improve selectors
   - Add retry logic where needed

3. Test Peak Capacity
   - Run large batch (500+ companies)
   - Monitor resource usage
   - Ensure no memory leaks
```

### **Phase 3: Scaling (Month 2+)**

```bash
1. Enable Parallel Processing
   - Set MAX_WORKERS=2
   - Monitor RAM (should be ~4.5 GB)
   - Monitor CPU (should be ~75-85%)
   - Target: 2,000 companies/day

2. Add Caching (Optional)
   - Install Redis: sudo apt install redis-server
   - Cache company lookups (24h)
   - Reduce redundant searches

3. Add Database (Optional)
   - Install PostgreSQL
   - Store results in DB
   - Enable API queries
```

---

## 🔍 Monitoring Dashboard

### **Key Metrics to Track**

```yaml
System Health:
  ├── CPU Usage: Target 60-80%, Alert >90%
  ├── RAM Usage: Target 40-60%, Alert >80%
  ├── Disk Usage: Target <70%, Alert >85%
  └── Swap Usage: Target <10%, Alert >50%

Application Performance:
  ├── Success Rate: Target >95%, Alert <90%
  ├── Avg Time/Company: Target 15-20s
  ├── Error Rate: Target <5%, Alert >10%
  └── Queue Length: Monitor for backlogs

Business Metrics:
  ├── Companies/Day: Track trend
  ├── Companies/Hour: Peak vs average
  ├── Cost per Company: ~$0.00043
  └── Uptime: Target 99%+
```

### **Monitoring Commands**

```bash
# Quick health check
~/automation_platform/deployment/monitor.sh

# Real-time resource usage
htop

# Service status
systemctl status automation-backend nginx

# Live logs
tail -f ~/automation_platform/automation_data/logs/automation.log

# Today's processing count
grep "$(date +%Y-%m-%d)" ~/automation_platform/automation_data/logs/automation.log | grep -c "Processing Row"

# Success rate today
TOTAL=$(grep "$(date +%Y-%m-%d)" ~/automation_platform/automation_data/logs/automation.log | grep -c "Processing Row")
SUCCESS=$(grep "$(date +%Y-%m-%d)" ~/automation_platform/automation_data/logs/automation.log | grep -c "SUCCESS")
echo "Success rate: $(echo "scale=1; $SUCCESS * 100 / $TOTAL" | bc)%"
```

---

## 🚀 Expected Performance Timeline

### **Month 1: Foundation**
```
Setup complete: Day 1
First successful run: Day 1
Daily automation: Day 2-7
Optimization phase: Week 2-4
Stable operation: Week 4

Processing capacity:
- Week 1: 300-500 companies/day
- Week 2: 500-800 companies/day  
- Week 3: 800-1200 companies/day
- Week 4: 1000-1500 companies/day
```

### **Month 2-3: Optimization**
```
Parallel processing: Month 2
Caching layer: Month 2
Database integration: Month 3
API authentication: Month 3

Processing capacity:
- Month 2: 1500-2000 companies/day
- Month 3: 2000-3000 companies/day
```

### **Month 4+: Mature Operation**
```
Automated scaling: Month 4
Advanced monitoring: Month 4
Performance tuning: Ongoing

Processing capacity:
- Sustained: 2000-3000 companies/day
- Peak: 5000+ companies/day (short bursts)
```

---

## 💾 Storage Management

### **Storage Growth Projection**

```
Month 1:
├── Input CSVs: 1 GB
├── Output CSVs: 2 GB
├── Logs: 500 MB
├── Chrome cache: 1 GB
└── Total used: ~10 GB / 100 GB (10%)

Month 6:
├── Input CSVs: 3 GB
├── Output CSVs: 8 GB
├── Logs: 2 GB
├── Chrome cache: 2 GB
├── Database (if added): 5 GB
└── Total used: ~25 GB / 100 GB (25%)

Month 12:
├── Input CSVs: 5 GB
├── Output CSVs: 15 GB
├── Logs: 3 GB (with rotation)
├── Chrome cache: 3 GB
├── Database: 10 GB
└── Total used: ~40 GB / 100 GB (40%)

Storage will NOT be a bottleneck for 2+ years
```

---

## 📈 Scaling Decision Matrix

### **When to Increase Resources**

```
Stay on Conservative (1 worker):
✅ Processing <500 companies/day
✅ RAM usage <40%
✅ CPU usage <70%
✅ Success rate >95%
✅ No performance complaints

Switch to Balanced (1 worker optimized):
✅ Processing 500-1000 companies/day
✅ RAM usage 40-50%
✅ CPU usage 70-80%
✅ Success rate maintained >95%
✅ Want faster processing

Switch to Aggressive (2 workers):
✅ Processing >1000 companies/day
✅ RAM usage 50-60%
✅ CPU usage 80-90%
✅ Success rate acceptable >93%
✅ Need parallel processing

Switch to Maximum (3 workers):
✅ Processing >2000 companies/day
✅ RAM usage 60-75%
✅ CPU usage 90-95%
✅ Success rate acceptable >93%
✅ Need maximum throughput
```

---

**This architecture is optimized specifically for your Hostinger KVM 2 plan and will serve you excellently for 12-24 months!** 🚀

**Version:** 1.0.0 - KVM 2 Optimized  
**Date:** February 1, 2026  
**Server:** Hostinger KVM 2 (2 vCPU, 8GB RAM, 100GB NVMe)
