# 🔄 Complete Workflow Diagram - KVM 2 Automation Platform

## 📊 Visual Process Flow

### **High-Level Overview**

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AUTOMATION PLATFORM WORKFLOW                       │
│                   Hostinger KVM 2 (2 vCPU, 8GB RAM)                  │
└──────────────────────────────────────────────────────────────────────┘

┌─────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│  INPUT  │ ──→ │ PROCESS  │ ──→ │  EXTRACT  │ ──→ │  OUTPUT  │
│   CSV   │     │  SEARCH  │     │  CONTACTS │     │   CSV    │
└─────────┘     └──────────┘     └───────────┘     └──────────┘
     │                │                  │                │
     ▼                ▼                  ▼                ▼
 Upload to      CompanyInfo       Phone/Email      Download
 VPS Server      Website          Extraction        Results
```

---

## 🎬 Detailed Step-by-Step Flow

### **PHASE 1: DATA INPUT**

```
User Action
    │
    ▼
┌─────────────────────────────────────────┐
│  Upload CSV File                        │
│  Method 1: Web Interface (Browser)     │
│  Method 2: API (curl/Postman)          │
│  Method 3: SCP/SFTP to server           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  File Received by Backend API           │
│  Endpoint: POST /api/upload-csv         │
│  Location: Port 8000                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Validate File                          │
│  - Check file format (.csv)             │
│  - Verify required columns (CB-CF)      │
│  - Check file size (<100MB)             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Save to Input Directory                │
│  Path: /automation_data/input/          │
│  Name: input.csv or custom name         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Confirm Upload Success                 │
│  Return: {"status": "success",          │
│           "filename": "input.csv",      │
│           "rows": 150}                  │
└─────────────────────────────────────────┘
```

---

### **PHASE 2: TRIGGER AUTOMATION**

```
Two Trigger Methods:

A) Manual Trigger                    B) Scheduled Trigger
    │                                    │
    ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│ API Call:        │              │ Cron Job:        │
│ POST /run-auto   │              │ 0 2 * * *        │
│ OR               │              │ (Daily 2 AM)     │
│ Click "Start"    │              │                  │
└────────┬─────────┘              └────────┬─────────┘
         │                                 │
         └─────────────┬───────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Execute run_automation.sh  │
         └─────────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Pre-flight Checks:         │
         │  ✓ Chrome installed         │
         │  ✓ Python venv active       │
         │  ✓ Input file exists        │
         │  ✓ Disk space available     │
         └─────────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Start Virtual Display      │
         │  xvfb-run (headless mode)   │
         └─────────────┬───────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  Launch Python main.py      │
         └─────────────────────────────┘
```

---

### **PHASE 3: DATA PROCESSING**

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PROCESSING LOOP                              │
└─────────────────────────────────────────────────────────────────────┘

START: main.py execution
    │
    ▼
┌──────────────────────────────────────┐
│ STEP 0: Read Input CSV               │
│                                      │
│ Module: ExcelReader                  │
│ Action: Parse CSV file               │
│ Extract:                             │
│   - Column CB: Company Name          │
│   - Column CC: Street Address        │
│   - Column CD: House Number          │
│   - Column CF: City                  │
│ Combine: CC + CD + CF = Full Address│
│                                      │
│ Output: List of companies            │
│ Example: [                           │
│   {row: 2, company: "ABC Ltd",       │
│    address: "Main St 123 Amsterdam"} │
│   {row: 3, company: "XYZ BV", ...}   │
│ ]                                    │
│                                      │
│ Time: ~2s for 100 rows               │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Initialize Browser Session           │
│                                      │
│ Module: BrowserAutomation            │
│ Action:                              │
│   - Launch Chrome (headless)         │
│   - Load profile from disk           │
│   - Set timeouts                     │
│   - Maximize window (virtual)        │
│                                      │
│ Resources:                           │
│   - RAM: ~800 MB per instance        │
│   - CPU: ~10% idle, 40% active       │
│                                      │
│ Time: ~3s startup                    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│ FOR EACH COMPANY IN LIST (Sequential or Parallel)               │
│                                                                  │
│ Current Company: Row 2, "ABC Ltd", "Main St 123 Amsterdam"     │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────────┐
│ STEP 1: Search by Company Name                                   │
│                                                                   │
│ Module: CompanyInfoSearcher                                       │
│ Action:                                                           │
│   1. Navigate to CompanyInfo.com/search                          │
│   2. Check if logged in                                          │
│      ├─ If NOT logged in: Auto-login with credentials           │
│      └─ If logged in: Continue                                   │
│   3. Find search input field                                     │
│      - Try: input[type="search"]                                 │
│      - Try: input[type="text"]                                   │
│      - Try: input#search                                         │
│   4. Clear field and enter: "ABC Ltd"                            │
│   5. Press Enter or click Search button                          │
│   6. Wait for results page to load                               │
│      - Timeout: 10s (configurable)                               │
│      - Smart wait: Returns immediately when ready                │
│                                                                   │
│ Time: ~5s (cached login) or ~10s (fresh login)                   │
└──────────────┬────────────────────────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────────┐
│ STEP 2: Count Search Results                                     │
│                                                                   │
│ Module: CompanyInfoSearcher._count_search_results()               │
│ Action:                                                           │
│   1. Parse page HTML                                             │
│   2. Look for result count text                                  │
│      - "322 resultaten" → 322 results                            │
│      - "1 resultaat" → 1 result                                  │
│      - "geen resultaten" → 0 results                             │
│   3. If text not found, count visible result rows                │
│                                                                   │
│ Decision Tree:                                                    │
│                                                                   │
│   Found exactly 1 result?                                        │
│   ├─ YES → Go to STEP 3A (Open Result)                          │
│   └─ NO  → Go to STEP 3B (Search by Address)                    │
│                                                                   │
│ Time: <1s                                                         │
└──────────────┬────────────────────────────────────────────────────┘
               │
               ├─────────────────────┬─────────────────────────────┐
               │                     │                             │
        [1 Result Found]    [0 or Multiple Results]               │
               │                     │                             │
               ▼                     ▼                             │
┌──────────────────────────┐  ┌──────────────────────────────────┐│
│ STEP 3A: Open Company    │  │ STEP 3B: Search by Address       ││
│                          │  │                                  ││
│ Action:                  │  │ Action:                          ││
│   - Click first result   │  │   1. Clear search field          ││
│   - Wait for page load   │  │   2. Enter full address:         ││
│   - Verify company page  │  │      "Main St 123 Amsterdam"     ││
│                          │  │   3. Press Enter                 ││
│ Time: ~2s                │  │   4. Wait for results            ││
└────────┬─────────────────┘  │   5. Count results               ││
         │                    │                                  ││
         │                    │ Decision:                        ││
         │                    │   - 1 result? → Click it         ││
         │                    │   - 0 or many? → Mark FAILED     ││
         │                    │                                  ││
         │                    │ Time: ~5s                        ││
         │                    └──────────┬───────────────────────┘│
         │                               │                        │
         └───────────────┬───────────────┘                        │
                         │                                        │
                         ▼                                        │
         ┌───────────────────────────────────────┐               │
         │ On Company Page?                      │               │
         ├─ YES → Continue to STEP 4             │               │
         └─ NO  → Mark FAILED, Skip to STEP 6    │               │
                         │                                        │
                         ▼                                        │
┌────────────────────────────────────────────────────────────────────┐
│ STEP 4: Extract Contact Information                               │
│                                                                    │
│ Module: CompanyInfoSearcher.extract_contact_info()                │
│ Action:                                                            │
│   1. Parse HTML of company detail page                            │
│   2. Find phone numbers:                                          │
│      Strategy:                                                    │
│        - Search for patterns: 06-XXXXXXXX, 06XXXXXXXX            │
│        - Search for patterns: 05-XXXXXXXX, 05XXXXXXXX            │
│        - Search for patterns: +31 6, +31 5                       │
│        - Normalize to: 0612345678 format                         │
│      Priority:                                                    │
│        1st choice: 06 numbers (mobile)                           │
│        2nd choice: 05 numbers (landline)                         │
│                                                                    │
│   3. Find email addresses:                                        │
│      Strategy:                                                    │
│        - Regex: [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}  │
│        - Look in: mailto: links, text content                    │
│        - Validate format                                         │
│                                                                    │
│   4. Extract business name (if different from search)            │
│   5. Extract owner name (if available)                           │
│                                                                    │
│ Output: {                                                         │
│   phone: "0612345678" or "NULL",                                 │
│   email: "info@abc.nl" or "NULL",                                │
│   business: "ABC Ltd" or "NULL",                                 │
│   owner: "John Doe" or "NULL"                                    │
│ }                                                                 │
│                                                                    │
│ Time: ~2s                                                         │
└──────────────┬─────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────┐
│ STEP 5: Retry Logic (If Needed)                                   │
│                                                                    │
│ Check Results:                                                     │
│   - Phone found? ✓                                                │
│   - Email found? ✓                                                │
│                                                                    │
│ If BOTH NULL (nothing found):                                     │
│   Decision:                                                        │
│     - Is this a permanent error? (404, not found, etc.)           │
│       YES → Mark FAILED, no retry                                 │
│       NO  → Retry once (max 2 attempts)                           │
│                                                                    │
│   Retry Strategy:                                                  │
│     1. Wait 2 seconds                                             │
│     2. Check browser health                                       │
│     3. If browser crashed, restart it                             │
│     4. Go back to STEP 1                                          │
│                                                                    │
│ If SUCCESS (at least phone OR email found):                       │
│   → Continue to STEP 6                                            │
│                                                                    │
│ Time: 0s (if success) or ~15s (if retry)                         │
└──────────────┬─────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────┐
│ STEP 6: Save Results Immediately                                  │
│                                                                    │
│ Module: CSVWriter.write_results()                                 │
│ Action:                                                            │
│   1. Load existing output CSV (or create if first run)            │
│      Filename: DONE_input.csv                                     │
│   2. Find matching row by row_number (from original CSV)          │
│   3. Update columns:                                              │
│      - CG (Phone): Write extracted phone or "NULL"                │
│      - CH (Email): Write extracted email or "NULL"                │
│      - Business: Write business name (optional)                   │
│      - Owner: Write owner name (optional)                         │
│   4. Save CSV immediately (don't wait for all rows)               │
│      Benefit: No data loss if crash happens                       │
│   5. Handle file locks:                                           │
│      - Retry up to 3 times if file is locked                      │
│      - Wait 1 second between retries                              │
│                                                                    │
│ Output CSV Format:                                                │
│   CB,CC,CD,CF,CG,CH,Business,Owner                               │
│   ABC Ltd,Main St,123,Amsterdam,0612345678,info@abc.nl,ABC,John │
│                                                                    │
│ Logging:                                                          │
│   ✓ Saved row 2 to CSV: Phone=0612345678, Email=info@abc.nl     │
│                                                                    │
│ Time: <1s                                                         │
└──────────────┬─────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────┐
│ Progress Update                                                    │
│                                                                    │
│ Log to console:                                                    │
│   ========================================                         │
│   Processing Row 2/150 (Excel Row 2)                             │
│   ========================================                         │
│   Company: ABC Ltd                                                │
│   Address: Main St 123 Amsterdam                                  │
│   → Phone: 0612345678                                             │
│   → Email: info@abc.nl                                            │
│   → Business: ABC Ltd                                             │
│   → Owner: John Doe                                               │
│   ✓ SUCCESS                                                       │
│                                                                    │
└──────────────┬─────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────┐
│ Next Company?                                                      │
│                                                                    │
│ Check if more rows exist:                                         │
│   ├─ YES (Row 3/150) → Loop back to STEP 1                       │
│   └─ NO  (Last row processed) → Go to PHASE 4                    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

### **PHASE 4: COMPLETION & CLEANUP**

```
All Companies Processed
    │
    ▼
┌─────────────────────────────────────────┐
│ Generate Summary Statistics             │
│                                         │
│ Calculate:                              │
│   - Total rows processed: 150           │
│   - Successful extractions: 142         │
│   - Failed: 8                           │
│   - Success rate: 94.7%                 │
│   - Total time: 62 minutes              │
│   - Avg time per company: 24.8s         │
│                                         │
│ Log:                                    │
│   ==============================        │
│   AUTOMATION SUMMARY                    │
│   ==============================        │
│   Total Processed: 150                  │
│   Successful: 142                       │
│   Failed: 8                             │
│   Output File: DONE_input.csv          │
│   ==============================        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Browser Cleanup                         │
│                                         │
│ Actions:                                │
│   1. Clear browser cache                │
│   2. Clear session storage              │
│   3. Delete cookies (except login)      │
│   4. Close all tabs                     │
│   5. Quit Chrome process                │
│   6. Free memory (~800 MB per instance) │
│                                         │
│ Time: ~2s                               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ File Operations                         │
│                                         │
│ Actions:                                │
│   1. Verify output CSV exists           │
│   2. Check file size                    │
│   3. Set permissions (644)              │
│   4. Create backup (optional)           │
│   5. Move to output directory           │
│                                         │
│ Final Location:                         │
│   /automation_data/output/DONE_input.csv│
│                                         │
│ Time: <1s                               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Log Rotation & Cleanup                  │
│                                         │
│ Actions:                                │
│   1. Rotate log file if >100 MB         │
│   2. Compress old logs                  │
│   3. Delete logs older than 30 days     │
│   4. Update run statistics              │
│   5. Send notification (if configured)  │
│                                         │
│ Time: <1s                               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Exit & Report                           │
│                                         │
│ Return code: 0 (success) or 1 (error)   │
│ Update systemd status                   │
│ Release process lock                    │
│                                         │
│ ✓ CompanyInfo Automation - COMPLETE    │
└─────────────────────────────────────────┘
```

---

### **PHASE 5: USER RETRIEVAL**

```
User wants results
    │
    ▼
┌─────────────────────────────────────────────┐
│ Method 1: Download via Web Interface       │
│                                             │
│ User → Browser → HTTPS → Nginx → Backend   │
│   │                                         │
│   └─ GET /api/list-outputs                 │
│      Response: ["DONE_input.csv"]          │
│                                             │
│   └─ GET /api/download-output/DONE_input.csv│
│      Response: CSV file stream             │
│      Browser: Auto-download to Downloads/  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Method 2: Download via API                  │
│                                             │
│ curl -O http://vps-ip/api/download-output/\ │
│      DONE_input.csv                         │
│                                             │
│ Saves to: ./DONE_input.csv                 │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Method 3: Direct SCP/SFTP                   │
│                                             │
│ scp automation@vps-ip:/automation_data/\    │
│     output/DONE_input.csv ./                │
│                                             │
│ Saves to: current directory                │
└─────────────────────────────────────────────┘
```

---

## ⚡ Performance Timeline

### **Processing 100 Companies - Detailed Timeline**

```
┌────────────────────────────────────────────────────────────────┐
│                      TIME BREAKDOWN                             │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  00:00 - Setup & Initialization                                │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 30s       │
│  - Load Python environment                                     │
│  - Read CSV file                                               │
│  - Launch Chrome browser                                       │
│  - Check CompanyInfo login                                     │
│                                                                 │
│  00:30 - Company 1-20 Processing                               │
│  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 8 min      │
│  - Search & extract (25s avg each)                            │
│  - Some fast (15s), some slow (40s)                           │
│  - Save after each company                                     │
│                                                                 │
│  08:30 - Company 21-50 Processing                              │
│  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 12 min     │
│  - Browser session warmed up                                   │
│  - Faster average (22s each)                                   │
│  - Cache hits on repeated addresses                            │
│                                                                 │
│  20:30 - Company 51-80 Processing                              │
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░ 12 min     │
│  - Consistent performance                                      │
│  - Occasional retries for failed searches                      │
│                                                                 │
│  32:30 - Company 81-100 Processing                             │
│  ████████████████████████████████░░░░░░░░░░░░░░░░ 8 min      │
│  - Final batch processing                                      │
│  - Fewer failures (learned patterns)                           │
│                                                                 │
│  40:30 - Cleanup & Finalization                                │
│  ████████████████████████████████████░░░░░░░░░░░░ 30s        │
│  - Close browser                                               │
│  - Verify output file                                          │
│  - Generate summary                                            │
│                                                                 │
│  TOTAL TIME: ~41 minutes for 100 companies                     │
│  Average: 24.6 seconds per company                             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Optimization Opportunities

### **Where Time is Spent (Per Company)**

```
Total Time: 25 seconds
├─ Navigation: 3s (12%)
│  └─ Can optimize: Page load timeout
│
├─ Search: 5s (20%)
│  └─ Can optimize: Reduce IMPLICIT_WAIT
│
├─ Results parsing: 2s (8%)
│  └─ Optimized: Fast CSS selectors
│
├─ Contact extraction: 8s (32%)
│  └─ Can optimize: Better regex patterns
│
├─ Data saving: 1s (4%)
│  └─ Optimized: Direct CSV write
│
├─ Page load waits: 4s (16%)
│  └─ Can optimize: Smart wait conditions
│
└─ Other overhead: 2s (8%)
   └─ Logging, error handling

Optimization Potential: 30-40% time reduction possible
Optimized time: 15-18 seconds per company
```

---

## 🔧 Resource Usage During Workflow

### **RAM Usage Over Time**

```
8 GB Total RAM

7 GB │
     │
6 GB │                         ╭──────────────────────╮
     │                         │  Peak Processing     │
5 GB │                    ╭────┤  (3 Chrome workers) │
     │                    │    │                      │
4 GB │              ╭─────┤    ╰──────────────────────╯
     │         ╭────┤     │
3 GB │    ╭────┤    │     │              ╭────╮
     │    │    │    │     │              │    │
2 GB │────┤    │    │     │──────────────┤    │────
     │    │    │    │     │              │    │
1 GB │    │    │    │     │              │    │
     │    │    │    │     │              │    │
0 GB └────┴────┴────┴─────┴──────────────┴────┴────
     Boot 1   2-3  Peak  Normal         Cleanup Idle
          Chr  Chr  Load  Processing    Phase

Legend:
- Idle: ~800 MB (System)
- 1 Chrome: ~1.6 GB
- 2 Chrome: ~2.4 GB
- 3 Chrome: ~3.2 GB
- Peak load: ~5 GB (with backend, nginx, buffers)
- Spare: 2-3 GB available
```

### **CPU Usage Over Time**

```
100%│     ╭╮  ╭╮ ╭╮    ╭╮     ╭╮
    │     ││  ││ ││    ││     ││
 80%│   ╭─┤│╭─┤│╭┤│╭───┤│╭────┤│──
    │   │ │││ │││││   │││    ││
 60%│ ╭─┤ │││ │││││   │││    ││
    │ │ │ │││ │││││   │││    ││
 40%│─┤ │ │││ │││││   │││    ││────
    │ │ │ └┘│ └┘││└───┘│└────┘│
 20%│ │ │   │   ││     │      │
    │ │ │   │   ││     │      │
  0%└─┴─┴───┴───┴┴─────┴──────┴────
    Boot Search Extract Save  Cleanup

Legend:
- Idle: 10-15% (System processes)
- Search phase: 60-70% (Network + parsing)
- Extract phase: 80-90% (CPU intensive parsing)
- Save phase: 40-50% (Disk I/O)
- Average: 60-70% sustained
- Spare: 30-40% for bursts
```

---

## 🎪 Parallel Processing Workflow (Phase 2)

### **With MAX_WORKERS=2 (2 Chrome Instances)**

```
Worker 1                          Worker 2
   │                                 │
   ├─ Company 1 (Row 2)              ├─ Company 2 (Row 3)
   │  └─ Search → Extract → Save    │  └─ Search → Extract → Save
   │     25s                         │     23s
   │                                 │
   ├─ Company 3 (Row 4)              ├─ Company 4 (Row 5)
   │  └─ Search → Extract → Save    │  └─ Search → Extract → Save
   │     27s                         │     22s
   │                                 │
   ├─ Company 5 (Row 6)              ├─ Company 6 (Row 7)
   │  └─ ...                         │  └─ ...
   │                                 │
   └─ Processing continues           └─ Processing continues

Timeline Comparison:
Sequential (1 worker):   100 companies × 25s = 2,500s (41 min)
Parallel (2 workers):    100 companies × 12.5s = 1,250s (21 min)
Time saved: 50% reduction!
```

---

## 📊 Success/Failure Decision Tree

```
Start Processing Company
        │
        ▼
   Search by Name
        │
        ├─────────────────┬─────────────────┐
        │                 │                 │
     1 Result         Multiple          No Results
        │                 │                 │
        ▼                 ▼                 ▼
   Click Result     Search by Addr    Search by Addr
        │                 │                 │
        ▼                 ▼                 ▼
   Extract Info      1 Result Found?   1 Result Found?
        │             YES │   NO        YES │   NO
        ▼                 ▼   │            ▼   │
   Phone/Email        Click   │       Click   │
   Found?             Result  │       Result  │
   YES │   NO             │   │           │   │
       ▼   │             ▼   ▼           ▼   ▼
   SUCCESS │         Extract Info    Extract Info
           │         Phone/Email?    Phone/Email?
           │         YES │   NO      YES │   NO
           │             ▼   │           ▼   │
           │         SUCCESS │       SUCCESS │
           │                 │               │
           └─────────────────┴───────────────┘
                             │
                             ▼
                         Mark FAILED
                         Status: "Not found"
```

---

## 🎯 Real-World Scenarios

### **Scenario 1: Perfect Match**
```
Input: "ABC Company", "Main St 123 Amsterdam"
   ↓
Search by name → 1 result found
   ↓
Extract contacts → Phone: 0612345678, Email: info@abc.nl
   ↓
Save to CSV → SUCCESS
Time: 18 seconds
```

### **Scenario 2: Common Name (Multiple Results)**
```
Input: "Bakkerij", "Kerkstraat 45 Utrecht"
   ↓
Search by name → 50 results found
   ↓
Search by address → 1 result found
   ↓
Extract contacts → Phone: 0687654321, Email: info@bakkerij.nl
   ↓
Save to CSV → SUCCESS
Time: 28 seconds
```

### **Scenario 3: Not Found**
```
Input: "Nonexistent BV", "Fake St 999 Nowhere"
   ↓
Search by name → 0 results
   ↓
Search by address → 0 results
   ↓
Save to CSV → FAILED (Phone: NULL, Email: NULL)
Time: 15 seconds (fast fail)
```

---

**This workflow processes 500-3,000 companies/day on your KVM 2 VPS!** 🚀

**Version:** 1.0.0 - KVM 2 Optimized  
**Date:** February 1, 2026  
**Server:** Hostinger KVM 2 (2 vCPU, 8GB RAM, 100GB NVMe)
