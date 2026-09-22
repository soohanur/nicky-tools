"""
Parallel worker implementation for automation tasks
Supports multi-threaded processing with anti-detection measures
Includes browser recycling, crash recovery, and cancellation support
"""
import time
import random
import logging
from threading import Lock, Event
from typing import Dict, List, Any, Optional


from datetime import datetime

logger = logging.getLogger(__name__)

# Browser recycling config
BROWSER_RECYCLE_INTERVAL = 40  # Restart Chrome every 40 rows to prevent memory issues


class CancellationToken:
    """Thread-safe cancellation token that can be shared across workers"""
    
    def __init__(self):
        self._cancelled = Event()
    
    def cancel(self):
        """Signal cancellation to all workers"""
        self._cancelled.set()
        logger.warning("🛑 Cancellation signal sent to all workers")
    
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested"""
        return self._cancelled.is_set()
    
    def reset(self):
        """Reset cancellation state"""
        self._cancelled.clear()


class ParallelProgress:
    """Thread-safe progress tracker for parallel workers"""
    
    def __init__(self):
        self.lock = Lock()
        self.processed = 0
        self.successful = 0
        self.failed = 0
    
    def increment_processed(self):
        with self.lock:
            self.processed += 1
    
    def increment_successful(self):
        with self.lock:
            self.successful += 1
    
    def increment_failed(self):
        with self.lock:
            self.failed += 1
    
    def get_stats(self) -> Dict[str, int]:
        with self.lock:
            return {
                "processed": self.processed,
                "successful": self.successful,
                "failed": self.failed
            }


class ThreadSafeCSVWriter:
    """Thread-safe CSV writer wrapper"""
    
    def __init__(self, csv_writer):
        self.csv_writer = csv_writer
        self.lock = Lock()
    
    def append_row(self, row):
        with self.lock:
            self.csv_writer.append_row(row)


def _create_browser_and_searcher(worker_id: int, email: str, password: str, implicit_wait: int, page_load_timeout: int):
    """
    Create a new browser instance and searcher.
    Used for initial creation and crash recovery.
    
    Returns:
        Tuple of (browser, searcher) or (None, None) on failure
    """
    from scraply.src.modules.browser_automation import BrowserAutomation
    from scraply.src.modules.companyinfo_searcher import CompanyInfoSearcher
    
    try:
        profile_name = f"Worker_{worker_id}"
        logger.info(f"🔄 Worker {worker_id}: Creating browser (profile: {profile_name})")
        
        browser = BrowserAutomation(
            profile_path=None,  # No profile in Docker
            profile_name=profile_name,
            headless=True,  # Always headless
            implicit_wait=implicit_wait
        )
        browser.__enter__()
        
        searcher = CompanyInfoSearcher(
            browser=browser,
            base_url='https://company.info',
            timeout=page_load_timeout,
            email=email,
            password=password
        )
        
        return browser, searcher
        
    except Exception as e:
        logger.error(f"🤖 Worker {worker_id}: Failed to create browser - {e}")
        return None, None


def _close_browser_safely(browser, worker_id: int):
    """Safely close a browser instance"""
    if browser:
        try:
            browser.__exit__(None, None, None)
            logger.info(f"🤖 Worker {worker_id}: Browser closed")
        except Exception as e:
            logger.warning(f"🤖 Worker {worker_id}: Browser close error (ignored) - {e}")


def process_chunk_worker(
    worker_id: int,
    chunk: List[Dict],
    chunk_start_idx: int,
    total_rows: int,
    email: str,
    password: str,
    headless: bool,
    implicit_wait: int,
    page_load_timeout: int,
    col_company: str,
    col_street: str,
    col_house_number: str,
    col_city: str,
    csv_writer: ThreadSafeCSVWriter,
    progress_tracker: ParallelProgress,
    enable_anti_detection: bool,
    cancellation_token: Optional[CancellationToken] = None
) -> Dict[str, Any]:
    """
    Process a chunk of rows in a separate thread.
    Includes browser recycling, crash recovery, and cancellation support.
    
    Args:
        worker_id: Unique worker identifier (1, 2, etc.)
        chunk: List of rows to process
        chunk_start_idx: Starting index in global row list
        total_rows: Total number of rows across all workers
        email: CompanyInfo login email
        password: CompanyInfo login password
        headless: Run browser in headless mode
        implicit_wait: Browser implicit wait timeout
        page_load_timeout: Page load timeout
        col_company: Company name column
        col_street: Street address column
        col_house_number: House number column
        col_city: City column
        csv_writer: Thread-safe CSV writer
        progress_tracker: Thread-safe progress tracker
        enable_anti_detection: Enable random delays (anti-bot)
        cancellation_token: Shared cancellation token (optional)
        
    Returns:
        Dict with worker results
    """
    logger.info(f"🤖 Worker {worker_id}: Starting (processing {len(chunk)} rows)")
    
    # Anti-detection: Stagger start times
    if enable_anti_detection and worker_id > 1:
        stagger_delay = (worker_id - 1) * random.uniform(2, 3)
        logger.info(f"🤖 Worker {worker_id}: Waiting {stagger_delay:.1f}s before starting (anti-detection)")
        time.sleep(stagger_delay)
    
    browser = None
    searcher = None
    local_successful = 0
    local_failed = 0
    rows_since_browser_restart = 0
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 3  # Restart browser after 3 consecutive errors
    
    try:
        # Create initial browser
        browser, searcher = _create_browser_and_searcher(
            worker_id, email, password, implicit_wait, page_load_timeout
        )
        
        if not browser or not searcher:
            logger.error(f"🤖 Worker {worker_id}: Failed to create initial browser, aborting")
            return {
                "worker_id": worker_id,
                "status": "error",
                "error": "Failed to create initial browser",
                "successful": 0,
                "failed": len(chunk)
            }
        
        # Process chunk
        for chunk_idx, row in enumerate(chunk):
            global_idx = chunk_start_idx + chunk_idx + 1
            
            # CHECK CANCELLATION BEFORE EACH ROW
            if cancellation_token and cancellation_token.is_cancelled():
                logger.warning(f"🛑 Worker {worker_id}: Cancellation detected at row {global_idx}, stopping gracefully")
                # Write remaining rows as cancelled
                remaining = len(chunk) - chunk_idx
                for remaining_row in chunk[chunk_idx:]:
                    for i in range(1, 6):
                        remaining_row[f'NUMBER {i}'] = 'NULL'
                    remaining_row['EMAIL'] = 'NULL'
                    remaining_row['BUSINESS_NAME'] = 'NULL'
                    remaining_row['OWNER_NAME'] = 'NULL'
                    remaining_row['NOTE'] = 'CANCELLED: Job cancelled by user'
                    csv_writer.append_row(remaining_row)
                    local_failed += 1
                    progress_tracker.increment_failed()
                    progress_tracker.increment_processed()
                
                return {
                    "worker_id": worker_id,
                    "status": "cancelled",
                    "successful": local_successful,
                    "failed": local_failed,
                    "processed": len(chunk),
                    "cancelled_at_row": global_idx
                }
            
            # BROWSER RECYCLING: Restart browser every N rows to prevent memory issues
            if rows_since_browser_restart >= BROWSER_RECYCLE_INTERVAL:
                logger.info(f"♻️ Worker {worker_id}: Recycling browser after {rows_since_browser_restart} rows")
                _close_browser_safely(browser, worker_id)
                time.sleep(1)  # Brief pause before restart
                
                # Retry browser creation up to 5 times before giving up
                browser, searcher = None, None
                for retry in range(5):
                    browser, searcher = _create_browser_and_searcher(
                        worker_id, email, password, implicit_wait, page_load_timeout
                    )
                    if browser and searcher:
                        break
                    logger.warning(f"♻️ Worker {worker_id}: Browser recycle attempt {retry+1}/5 failed, retrying in {2*(retry+1)}s...")
                    time.sleep(2 * (retry + 1))
                
                if not browser or not searcher:
                    logger.error(f"🤖 Worker {worker_id}: Failed to recycle browser after 5 attempts at row {global_idx}")
                    # Mark remaining rows as failed
                    for remaining_row in chunk[chunk_idx:]:
                        for i in range(1, 6):
                            remaining_row[f'NUMBER {i}'] = 'NULL'
                        remaining_row['EMAIL'] = 'NULL'
                        remaining_row['BUSINESS_NAME'] = 'NULL'
                        remaining_row['OWNER_NAME'] = 'NULL'
                        remaining_row['NOTE'] = 'ERROR: Browser recycle failed'
                        csv_writer.append_row(remaining_row)
                        local_failed += 1
                        progress_tracker.increment_failed()
                        progress_tracker.increment_processed()
                    break
                
                rows_since_browser_restart = 0
                consecutive_errors = 0
            
            try:
                # Extract company info
                company_name = row.get(col_company, '').strip()
                street = row.get(col_street, '').strip()
                house_number = row.get(col_house_number, '').strip()
                city = row.get(col_city, '').strip()
                
                logger.info(f"🤖 Worker {worker_id} [{global_idx}/{total_rows}]: {company_name}")
                
                # Search company (with crash recovery)
                try:
                    contact_info = searcher.search_company(
                        company_name=company_name,
                        street=street,
                        house_number=house_number,
                        city=city
                    )
                    consecutive_errors = 0  # Reset on success
                    
                except Exception as search_err:
                    error_str = str(search_err)
                    consecutive_errors += 1
                    
                    # Check if this is a browser crash (connection refused, session not found, etc.)
                    is_browser_crash = any(phrase in error_str.lower() for phrase in [
                        'connection refused', 'session not found', 'session deleted',
                        'no such window', 'chrome not reachable', 'unable to connect',
                        'disconnected', 'target closed', 'browser has crashed'
                    ])
                    
                    if is_browser_crash or consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.warning(f"🔄 Worker {worker_id}: Browser crash detected or {consecutive_errors} consecutive errors, restarting browser...")
                        _close_browser_safely(browser, worker_id)
                        time.sleep(2)  # Wait before restart
                        
                        # Retry browser creation up to 5 times
                        browser, searcher = None, None
                        for retry in range(5):
                            browser, searcher = _create_browser_and_searcher(
                                worker_id, email, password, implicit_wait, page_load_timeout
                            )
                            if browser and searcher:
                                break
                            logger.warning(f"🔄 Worker {worker_id}: Browser restart attempt {retry+1}/5 failed, retrying in {2*(retry+1)}s...")
                            time.sleep(2 * (retry + 1))
                        
                        if browser and searcher:
                            rows_since_browser_restart = 0
                            consecutive_errors = 0
                            
                            # Retry the current row with new browser
                            logger.info(f"🔄 Worker {worker_id}: Retrying row {global_idx} with fresh browser")
                            try:
                                contact_info = searcher.search_company(
                                    company_name=company_name,
                                    street=street,
                                    house_number=house_number,
                                    city=city
                                )
                            except Exception as retry_err:
                                logger.error(f"🤖 Worker {worker_id}: Retry also failed - {retry_err}")
                                contact_info = {
                                    'phones': [],
                                    'email': None,
                                    'business': None,
                                    'owner': None,
                                    'note': f'ERROR: {str(retry_err)[:80]}'
                                }
                        else:
                            logger.error(f"🤖 Worker {worker_id}: Browser restart failed, marking remaining rows as failed")
                            # Write error for current row
                            for i in range(1, 6):
                                row[f'NUMBER {i}'] = 'NULL'
                            row['EMAIL'] = 'NULL'
                            row['BUSINESS_NAME'] = 'NULL'
                            row['OWNER_NAME'] = 'NULL'
                            row['NOTE'] = 'ERROR: Browser crashed and restart failed'
                            csv_writer.append_row(row)
                            local_failed += 1
                            progress_tracker.increment_failed()
                            progress_tracker.increment_processed()
                            
                            # Mark remaining rows as failed
                            for remaining_row in chunk[chunk_idx + 1:]:
                                for i in range(1, 6):
                                    remaining_row[f'NUMBER {i}'] = 'NULL'
                                remaining_row['EMAIL'] = 'NULL'
                                remaining_row['BUSINESS_NAME'] = 'NULL'
                                remaining_row['OWNER_NAME'] = 'NULL'
                                remaining_row['NOTE'] = 'ERROR: Worker browser dead'
                                csv_writer.append_row(remaining_row)
                                local_failed += 1
                                progress_tracker.increment_failed()
                                progress_tracker.increment_processed()
                            
                            return {
                                "worker_id": worker_id,
                                "status": "browser_dead",
                                "error": "Browser crashed and restart failed",
                                "successful": local_successful,
                                "failed": local_failed
                            }
                    else:
                        # Not a browser crash, just a regular error
                        contact_info = {
                            'phones': [],
                            'email': None,
                            'business': None,
                            'owner': None,
                            'note': f'ERROR: {str(search_err)[:80]}'
                        }
                
                # Process result (same logic as sequential)
                if contact_info.get('skip'):
                    # Skipped company (too many businesses)
                    for i in range(1, 6):
                        row[f'NUMBER {i}'] = 'NULL'
                    row['EMAIL'] = 'NULL'
                    row['BUSINESS_NAME'] = 'NULL'
                    row['OWNER_NAME'] = 'NULL'
                    row['NOTE'] = contact_info.get('note', 'SKIPPED: Too many businesses')
                    csv_writer.append_row(row)
                    local_failed += 1
                    progress_tracker.increment_failed()
                else:
                    # Get phone list
                    phones = contact_info.get('phones', [])
                    
                    # Populate NUMBER columns
                    for i in range(1, 6):
                        col_name = f'NUMBER {i}'
                        if i <= len(phones):
                            row[col_name] = phones[i-1]
                        else:
                            row[col_name] = 'NULL'
                    
                    # Add other results
                    row['EMAIL'] = contact_info.get('email', '') or 'NULL'
                    row['BUSINESS_NAME'] = contact_info.get('business', '') or 'NULL'
                    row['OWNER_NAME'] = contact_info.get('owner', '') or 'NULL'
                    row['NOTE'] = contact_info.get('note', '') or 'NULL'
                    
                    # Write to output
                    csv_writer.append_row(row)
                    
                    if phones or contact_info.get('email'):
                        local_successful += 1
                        progress_tracker.increment_successful()
                    else:
                        local_failed += 1
                        progress_tracker.increment_failed()
                
                progress_tracker.increment_processed()
                rows_since_browser_restart += 1
                
                # Anti-detection: Random delay between requests (looks more human)
                if enable_anti_detection and chunk_idx < len(chunk) - 1:  # Don't delay after last row
                    delay = random.uniform(1, 3)  # 1-3 seconds (safe with direct URL navigation)
                    logger.debug(f"🤖 Worker {worker_id}: Waiting {delay:.1f}s (anti-detection)")
                    # Sleep in small increments so cancellation is responsive
                    sleep_end = time.time() + delay
                    while time.time() < sleep_end:
                        if cancellation_token and cancellation_token.is_cancelled():
                            break
                        time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"🤖 Worker {worker_id} [{global_idx}]: Error - {e}")
                consecutive_errors += 1
                
                # Write error row
                for i in range(1, 6):
                    row[f'NUMBER {i}'] = 'NULL'
                row['EMAIL'] = 'NULL'
                row['BUSINESS_NAME'] = 'NULL'
                row['OWNER_NAME'] = 'NULL'
                row['NOTE'] = f'ERROR: {str(e)[:100]}'
                csv_writer.append_row(row)
                
                local_failed += 1
                progress_tracker.increment_failed()
                progress_tracker.increment_processed()
                rows_since_browser_restart += 1
        
        logger.info(f"🤖 Worker {worker_id}: Completed ✅ ({local_successful} success, {local_failed} failed)")
        
        return {
            "worker_id": worker_id,
            "status": "completed",
            "successful": local_successful,
            "failed": local_failed,
            "processed": len(chunk)
        }
        
    except Exception as e:
        logger.error(f"🤖 Worker {worker_id}: Fatal error - {e}", exc_info=True)
        return {
            "worker_id": worker_id,
            "status": "error",
            "error": str(e),
            "successful": local_successful,
            "failed": local_failed
        }
        
    finally:
        # Cleanup browser
        _close_browser_safely(browser, worker_id)
