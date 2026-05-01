"""Main automation orchestrator for CompanyInfo scraping."""
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config
from src.modules import create_browser, CSVReader, CSVWriter, CompanyInfoScraper
from src.modules.companyinfo_searcher import CompanyNotFoundException, BrowserConnectionError

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'logs' / 'scraply.log')
    ]
)
logger = logging.getLogger(__name__)

# Error tracking for browser restart
BROWSER_ERROR_THRESHOLD = 3
consecutive_errors = 0


class ScraplyAutomation:
    """Main automation class."""
    
    def __init__(self):
        """Initialize automation."""
        self.config = config
        self.browser = None
        self.scraper = None
        
    def run(self):
        """Run the complete automation workflow."""
        logger.info("=" * 60)
        logger.info("SCRAPLY AUTOMATION STARTED")
        logger.info("=" * 60)
        
        try:
            # Step 1: Read input CSV
            logger.info(f"Reading input file: {self.config.INPUT_CSV}")
            reader = CSVReader(self.config.PROJECT_ROOT / self.config.INPUT_CSV)
            rows = reader.read_all()
            
            if not rows:
                logger.error("No data found in input file")
                return False
            
            logger.info(f"Found {len(rows)} companies to process")
            
            # Step 2: Initialize browser
            logger.info("Starting browser...")
            self.browser = create_browser(
                profile_path=self.config.CHROME_PROFILE_PATH,
                headless=self.config.HEADLESS
            )
            
            if not self.browser:
                logger.error("Failed to start browser")
                return False
            
            # Step 3: Initialize scraper
            logger.info("Initializing CompanyInfo scraper...")
            self.scraper = CompanyInfoScraper(
                browser=self.browser,
                email=self.config.COMPANYINFO_EMAIL,
                password=self.config.COMPANYINFO_PASSWORD,
                base_url=self.config.COMPANYINFO_URL,
                timeout=self.config.COMPANYINFO_TIMEOUT
            )
            
            # Step 4: Setup output CSV
            logger.info(f"Setting up output file: {self.config.OUTPUT_CSV}")
            
            # Performance tracking
            start_time = time.time()
            
            # Get all columns from input + NUMBER 1-5 + EMAIL + BUSINESS_NAME + OWNER_NAME + NOTE (avoid duplicates)
            input_columns = list(rows[0].keys())
            output_columns = input_columns.copy()
            
            # Add up to 5 phone number columns (NUMBER 1 through NUMBER 5)
            for i in range(1, 6):
                col_name = f'NUMBER {i}'
                if col_name not in output_columns:
                    output_columns.append(col_name)
            
            if 'EMAIL' not in output_columns:
                output_columns.append('EMAIL')
            if 'BUSINESS_NAME' not in output_columns:
                output_columns.append('BUSINESS_NAME')
            if 'OWNER_NAME' not in output_columns:
                output_columns.append('OWNER_NAME')
            if 'NOTE' not in output_columns:
                output_columns.append('NOTE')
            
            writer = CSVWriter(
                self.config.PROJECT_ROOT / self.config.OUTPUT_CSV,
                output_columns
            )
            writer.write_header()
            
            # Step 5: Process each company
            logger.info("Starting company processing...")
            success_count = 0
            failed_count = 0
            
            for idx, row in enumerate(rows, 1):
                # Process with retry logic
                result = self._process_single_row_with_retry(row, idx, len(rows))
                
                # Write result to output
                output_row = row.copy()
                
                # Get phone list (06 number will be first if found)
                phones = result.get('phones', [])
                
                # Populate NUMBER 1, NUMBER 2, NUMBER 3, etc. columns
                for i in range(1, 6):
                    col_name = f'NUMBER {i}'
                    if i <= len(phones):
                        output_row[col_name] = phones[i-1]  # 06 number goes in NUMBER 1
                    else:
                        output_row[col_name] = ''  # Empty if no more numbers
                
                output_row['EMAIL'] = result.get('email', '') or 'NULL'
                output_row['BUSINESS_NAME'] = result.get('business', '') or 'NULL'
                output_row['OWNER_NAME'] = result.get('owner', '') or 'NULL'
                output_row['NOTE'] = result.get('note', '')
                writer.append_row(output_row)
                
                # Track success/failure/skipped
                if result.get('status') == 'SUCCESS':
                    success_count += 1
                    phones = result.get('phones', [])
                    phones_str = ', '.join(phones) if phones else 'N/A'
                    logger.info(f"[SUCCESS] Row {idx}/{len(rows)} - Phones: {phones_str}, Email: {result.get('email', 'N/A')}")
                elif result.get('status') == 'SKIPPED':
                    failed_count += 1
                    logger.info(f"[SKIPPED] Row {idx}/{len(rows)} - {result.get('business', 'Too many businesses')}")
                else:
                    failed_count += 1
                    logger.warning(f"[FAILED] Row {idx}/{len(rows)} - No contact info found")
                
                # Track consecutive errors for browser restart (skip SKIPPED companies)
                global consecutive_errors
                if result.get('status') == 'FAIL':
                    consecutive_errors += 1
                    if consecutive_errors >= BROWSER_ERROR_THRESHOLD:
                        logger.warning(f"[AUTO-RESTART] {consecutive_errors} consecutive failures - restarting browser...")
                        try:
                            self._restart_browser()
                            consecutive_errors = 0
                            logger.info("[RECOVERED] Browser restarted successfully")
                        except Exception as e:
                            logger.error(f"Browser restart failed: {e}")
                elif result.get('status') in ['SUCCESS', 'SKIPPED']:
                    consecutive_errors = 0
            
            # Summary
            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("AUTOMATION COMPLETED")
            logger.info("=" * 60)
            logger.info(f"Total processed: {len(rows)}")
            logger.info(f"Successful: {success_count}")
            logger.info(f"Failed: {failed_count}")
            success_rate = (success_count / len(rows) * 100) if len(rows) > 0 else 0
            logger.info(f"Success Rate: {success_rate:.1f}%")
            
            # Performance metrics
            elapsed_time = time.time() - start_time
            avg_time_per_row = elapsed_time / len(rows) if len(rows) > 0 else 0
            logger.info(f"Total Time: {elapsed_time:.1f}s ({avg_time_per_row:.1f}s per row)")
            
            logger.info(f"Output saved to: {self.config.OUTPUT_CSV}")
            logger.info("=" * 60)
            
            return True
            
        except KeyboardInterrupt:
            logger.warning("\nAutomation interrupted by user")
            return False
            
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return False
            
        finally:
            # Cleanup
            if self.browser:
                logger.info("Closing browser...")
                self.browser.close_browser()
    
    def _process_single_row_with_retry(self, row: Dict, idx: int, total: int) -> Dict:
        """
        Process single row with intelligent retry logic.
        
        Args:
            row: Row data dictionary
            idx: Current row index
            total: Total row count
            
        Returns:
            Result dictionary with phone, email, business, owner
        """
        max_attempts = 2
        result = {'phones': [], 'email': '', 'business': '', 'owner': '', 'note': '', 'status': 'FAIL'}
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing Row {idx}/{total}")
        logger.info(f"{'=' * 60}")
        
        # Get company data
        company_name = row.get(self.config.COL_COMPANY, '').strip()
        street = row.get(self.config.COL_STREET, '').strip()
        house_number = row.get(self.config.COL_HOUSE_NUMBER, '').strip()
        city = row.get(self.config.COL_CITY, '').strip()
        
        logger.info(f"Company: {company_name}")
        if street and city:
            logger.info(f"Address: {street} {house_number}, {city}")
        
        for attempt in range(1, max_attempts + 1):
            try:
                if attempt > 1:
                    logger.info(f"[RETRY] Attempt {attempt}/{max_attempts}")
                    time.sleep(1)  # Brief pause before retry
                
                # Search and extract
                contact_info = self.scraper.search_company(
                    company_name=company_name,
                    street=street,
                    house_number=house_number,
                    city=city
                )
                
                # Check if company should be skipped (too many businesses)
                if contact_info.get('skip'):
                    logger.info(f"[SKIPPED] {contact_info.get('reason', 'Unknown reason')}")
                    result['status'] = 'SKIPPED'
                    result['phones'] = []  # Empty list for skipped
                    result['email'] = 'SKIPPED'
                    result['business'] = contact_info.get('reason', 'Too many businesses')
                    result['owner'] = 'SKIPPED'
                    result['note'] = contact_info.get('note', 'SKIPPED: Too many businesses')
                    break  # No point retrying skipped companies
                
                result['phones'] = contact_info.get('phones', [])
                result['email'] = contact_info.get('email', '')
                result['business'] = contact_info.get('business', '')
                result['owner'] = contact_info.get('owner', '')
                result['note'] = contact_info.get('note', '')
                
                # Check if we got data
                if result['phones'] or result['email']:
                    result['status'] = 'SUCCESS'
                    if attempt > 1:
                        logger.info(f"[SUCCESS] Found data on attempt {attempt}")
                    break
                else:
                    # No data found - this is NOT a transient error, don't retry
                    logger.warning(f"[NOT FOUND] Company not in database or no contact info")
                    result['status'] = 'FAIL'
                    break  # Don't waste time retrying 'not found'
                    
            except (TimeoutException, NoSuchElementException) as e:
                logger.warning(f"[TIMEOUT] Page element timeout on attempt {attempt}: {e}")
                if attempt >= max_attempts:
                    result['status'] = 'FAIL'
                    break
                    
            except (WebDriverException, BrowserConnectionError) as e:
                logger.error(f"[BROWSER ERROR] {str(e)[:80]}")
                logger.warning("[AUTO-RECOVER] Restarting browser...")
                try:
                    self._restart_browser()
                    logger.info("[RECOVERED] Browser restarted, retrying...")
                    # Don't count this as failed attempt, retry immediately
                    continue
                except Exception as recovery_error:
                    logger.error(f"[FATAL] Browser recovery failed: {recovery_error}")
                    result['status'] = 'FAIL'
                    break
                    
            except CompanyNotFoundException:
                logger.info("[NOT FOUND] Company doesn't exist in database")
                result['status'] = 'FAIL'
                break  # No point retrying
                
            except Exception as e:
                logger.error(f"[UNEXPECTED] {type(e).__name__}: {str(e)[:80]}")
                if attempt >= max_attempts:
                    result['status'] = 'FAIL'
                    break
        
        return result
    
    def _restart_browser(self):
        """Restart browser to recover from errors."""
        try:
            # Clean up old browser
            if self.browser:
                try:
                    self.browser.driver.quit()
                except:
                    pass
            
            # Start fresh browser
            self.browser = create_browser(
                profile_path=self.config.CHROME_PROFILE_PATH,
                headless=self.config.HEADLESS
            )
            
            # Reinitialize scraper with new browser
            self.scraper = CompanyInfoScraper(
                browser=self.browser,
                email=self.config.COMPANYINFO_EMAIL,
                password=self.config.COMPANYINFO_PASSWORD,
                base_url=self.config.COMPANYINFO_URL,
                timeout=self.config.COMPANYINFO_TIMEOUT
            )
        except Exception as e:
            logger.error(f"Failed to restart browser: {e}")
            raise


def main():
    """Entry point."""
    automation = ScraplyAutomation()
    success = automation.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
