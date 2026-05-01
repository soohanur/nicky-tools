# Setup Guide - CompanyInfo Automation Software

## Quick Start

### 1. Install Dependencies
```powershell
cd "g:\Data Info"
pip install -r requirements.txt
```

### 2. Configure Settings
Edit `.env` file and update:
- **CHROME_PROFILE_PATH**: Your Chrome user data directory path
  - Windows: `C:/Users/YourUsername/AppData/Local/Google/Chrome/User Data`
  - Find it by visiting `chrome://version` and copying "Profile Path" (without the profile name at the end)
- **COMPANYINFO_URL**: The actual CompanyInfo search page URL
- **Column names** if different from CB, CC, CD, CF

### 3. Prepare Excel File
- Place your Excel file in: `data/input/input.xlsx`
- Make sure it has columns:
  - **CB**: Company Name
  - **CC, CD, CF**: Address parts
  - **CG**: Phone (output - can be empty)
  - **CH**: Email (output - can be empty)

### 4. Run the Automation
```powershell
python src/main.py
```

## Current Implementation Status

### ✓ Step 0 - Read Excel Data
- Reads company name from column CB
- Combines address from CC + CD + CF with spaces
- Processes all rows with data

### ✓ Step 1 - Search by Company Name
- Opens CompanyInfo in your logged-in Chrome browser
- Searches by company name
- If results found → clicks first result
- If no results → logs failure (Step 2 will handle this)

### ⏳ To Be Implemented (Next Steps)
- Step 2: Search by address when company name fails
- Step 3: Google fallback search
- Step 4: Extract phone (prefer 06, fallback 05) and email
- Step 5: Write results back to Excel

## Important Notes

1. **Browser Profile**: The automation uses your existing Chrome profile where you're already logged into CompanyInfo. Make sure Chrome is closed before running the script.

2. **Headless Mode**: Currently set to `False` so you can see what's happening. Change `HEADLESS_MODE=True` in `.env` if you want it to run in background.

3. **Website Selectors**: The CompanyInfo search uses generic selectors. You may need to update selectors in `src/modules/companyinfo_searcher.py` based on the actual CompanyInfo website structure.

## Troubleshooting

**Error: "Chrome profile in use"**
- Close all Chrome windows before running

**Error: "Search input not found"**
- The website structure may be different
- Check the actual CompanyInfo website and update selectors in `companyinfo_searcher.py`

**Error: "Excel file not found"**
- Make sure file is in `data/input/input.xlsx`
- Check file name and path

## Next Steps After Confirmation

Once you confirm Step 0 and Step 1 are working correctly, we'll implement:
1. Step 2: Address search logic
2. Contact extraction (phone + email)
3. Writing results back to Excel
