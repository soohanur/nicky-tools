# Parallel Processing Configuration

## How to Switch Modes

Edit `backend/app/tasks/automation_tasks.py` (line ~479):

```python
# PARALLEL PROCESSING CONFIG
NUM_WORKERS = 2              # <-- Change this number
ENABLE_ANTI_DETECTION = True # <-- Enable/disable delays
```

### Modes:

#### ✅ Parallel (2 Workers) - CURRENT MODE
```python
NUM_WORKERS = 2
ENABLE_ANTI_DETECTION = True
```
- **Speed:** ~2x faster (processes 2 companies simultaneously)
- **Anti-Detection:** Random delays 8-20 seconds between requests
- **Profiles:** Each worker uses separate Chrome profile
- **Stagger:** Worker 2 starts 10-20 seconds after Worker 1

#### 🔄 Sequential (Original) - SAFE FALLBACK
```python
NUM_WORKERS = 1
ENABLE_ANTI_DETECTION = False
```
- **Speed:** Normal (1 company at a time)
- **Anti-Detection:** None
- **Risk:** Lowest
- **Use:** If parallel causes issues

---

## Performance Estimates

### For 2000 rows:

| Mode | Workers | Anti-Detection | Time Estimate |
|------|---------|----------------|---------------|
| Sequential | 1 | No | ~15 hours |
| **Parallel** | **2** | **Yes** | **~8-10 hours** |
| Parallel | 2 | No | ~7-8 hours (⚠️ risky) |
| Parallel | 3 | Yes | ~6-7 hours (⚠️⚠️ higher detection risk) |

---

## Anti-Detection Features (When Enabled)

### 1. **Random Delays**
- Each worker waits 8-20 seconds (random) between companies
- Looks more human, less bot-like

### 2. **Staggered Start**
- Worker 1 starts immediately
- Worker 2 waits 10-20 seconds before starting
- Prevents simultaneous login attempts

### 3. **Separate Profiles**
- Worker 1: `Worker_1` profile
- Worker 2: `Worker_2` profile
- Cookies/sessions don't conflict

### 4. **Thread-Safe Operations**
- CSV writes are locked (no corruption)
- Progress tracking is synchronized
- Database updates are atomic

---

## How to Rollback (If Issues Occur)

### Quick Rollback:
1. Change `NUM_WORKERS = 1` in automation_tasks.py
2. Restart services:
   ```bash
   ssh root@76.13.145.229 "systemctl restart datainfo-celery"
   ```

### Full Rollback (Use Backup):
```bash
# Restore original file
cp backend/app/tasks/automation_tasks.py.backup backend/app/tasks/automation_tasks.py

# Redeploy
scp backend/app/tasks/automation_tasks.py root@76.13.145.229:/var/www/datainfo/backend/app/tasks/
ssh root@76.13.145.229 "systemctl restart datainfo-celery"
```

---

## Testing Recommendations

### 1. Test with Small File First
- Upload 50-100 row CSV
- Check results quality
- Compare to sequential mode

### 2. Monitor for Issues
- Watch Celery logs: `ssh root@76.13.145.229 "journalctl -u datainfo-celery -f"`
- Check for "Worker X" messages
- Look for errors/crashes

### 3. Check CompanyInfo Account
- If account gets blocked/throttled → Set `NUM_WORKERS = 1`
- If working fine → Can try `NUM_WORKERS = 3` (risky)

---

## Current Configuration
**Status:** ✅ Deployed to local, ready to deploy to VPS  
**Mode:** Parallel (2 workers)  
**Anti-Detection:** Enabled (8-20 sec delays)  
**Backup:** ✅ `automation_tasks.py.backup` created

---

## Deploy to VPS

```bash
# Deploy parallel version
scp backend/app/tasks/automation_tasks.py root@76.13.145.229:/var/www/datainfo/backend/app/tasks/
scp backend/app/tasks/parallel_worker.py root@76.13.145.229:/var/www/datainfo/backend/app/tasks/

# Restart services
ssh root@76.13.145.229 "systemctl restart datainfo-celery && systemctl restart datainfo-api"
```

---

## Troubleshooting

### Issue: Workers crash with browser errors
**Fix:** Reduce workers to 1 (sequential mode)

### Issue: CompanyInfo blocks/throttles account
**Fix:** Increase `ENABLE_ANTI_DETECTION` delays to 15-30 seconds

### Issue: CSV file corrupted
**Fix:** Thread-safe writer should prevent this, but rollback if occurs

### Issue: Progress not updating
**Check:** Database batch updates happen every 50 rows combined

---

**Note:** Start with 2 workers. If working well after 500 rows, can consider increasing. If any issues, immediately set `NUM_WORKERS = 1`.
