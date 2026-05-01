# Automation Platform - Scraply & More

## Overview
Professional automation platform featuring **Scraply** - an automated CompanyInfo.com data scraper, with architecture ready for additional tools.

### 🚀 Current Tools
- **Scraply** (v2.0) - CompanyInfo data extraction with phone and email discovery

### 🔮 Future Tools (Coming Soon)
- LinkedIn Profile Scraper
- Email Validator
- Phone Number Validator
- Data Enrichment Tool

## 📁 Project Structure (Tool-Isolated Architecture)

```
Data Info/                          # Project root
│
├── 📂 scraply/                     # ⭐ Scraply Tool (CompanyInfo Scraper)
│   ├── config.py                   # Scraply configuration
│   ├── main.py                     # Scraply entry point
│   ├── csv_files/                  # ⭐ Scraply CSV files (isolated)
│   │   ├── input/                  # 📥 Drop CSV files here
│   │   └── output/                 # 📤 Get results here
│   ├── chrome_profiles/            # ⭐ Scraply browser profiles
│   │   ├── default/                # Default Chrome profile
│   │   └── data_profile/           # Alternative profile
│   ├── logs/                       # ⭐ Scraply logs
│   │   └── scraply.log
│   └── src/                        # Scraply source modules
│
├── 📂 backend/                     # FastAPI REST API & Job Queue
│   ├── app/                        # Application code
│   │   ├── api/                    # API endpoints
│   │   ├── core/                   # Config, security, celery
│   │   ├── db/                     # Database models
│   │   ├── schemas/                # Pydantic schemas
│   │   └── tasks/                  # Background tasks (supports all tools)
│   ├── docker-compose.yml          # Multi-container deployment
│   ├── Dockerfile                  # Container image
│   └── requirements.txt            # Python dependencies
│
├── 📂 automation_data/             # Backend runtime storage
│   ├── input/                      # Backend API uploads
│   ├── output/                     # Backend API results
│   └── logs/                       # Backend logs
│
├── 📂 docs/                        # Documentation
│   ├── DEPLOYMENT_GUIDE.md         # Hostinger deployment
│   ├── KVM2_ARCHITECTURE.md        # VPS architecture
│   └── *.md                        # Additional guides
│
└── 📂 logs/                        # Global application logs
```

### 🎯 Architecture Benefits

✅ **Tool Isolation**: Each tool has its own CSV, profiles, and logs  
✅ **No Conflicts**: Future tools won't interfere with Scraply  
✅ **Easy Addition**: Add new tools with same pattern  
✅ **Clean Structure**: Everything organized by tool  
✅ **Scalable**: Supports unlimited tools  

## Features
- Excel data reading and writing
- Browser automation with existing session
- CompanyInfo search by company name and address
- Google fallback search
- Scalable modular architecture

## Setup
1. Install Python 3.8+
2. Install dependencies: `pip install -r requirements.txt`
3. Configure browser profile path in config
4. Place input Excel file in data/input/
5. Run: `python src/main.py`

## Workflow
- Step 0: Read Excel row data (Company Name, Address)
- Step 1: Search CompanyInfo by company name
- Step 2: Search by address if no results
- Step 3: Google fallback if needed
- Step 4: Extract phone (prefer 06, fallback 05) and email
- Step 5: Write results back to Excel
