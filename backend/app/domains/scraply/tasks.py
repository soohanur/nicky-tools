"""
Celery background tasks for automation tools
"""
import sys
import os
import time
import signal
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded, Terminated
from sqlalchemy import select

# Add project root to path
project_root = Path(__file__).resolve().parents[4]  # backend/app/domains/scraply -> repo root
sys.path.insert(0, str(project_root))

# Add scraply tool to path
scraply_path = project_root / "scraply"
sys.path.insert(0, str(scraply_path))

from app.core.task_queue import celery_app
from app.config import settings as backend_settings
from app.domains.jobs.models import Job, JobStatus, JobLog, ToolType
from app.core.db import AsyncSessionLocal
# Deferred import to avoid circular dependency
# from app.core.events import send_job_update

# Import Scraply tool (CompanyInfo scraper)
from src.modules import CSVReader, BrowserAutomation, CompanyInfoSearcher, CSVWriter
from src.config.settings import Config as scraply_config
import logging

logger = logging.getLogger(__name__)

# Global flag for termination
_termination_requested = False

def _signal_handler(signum, frame):
    """Handle termination signals."""
    global _termination_requested
    _termination_requested = True
    logger.warning(f"Received signal {signum}, requesting graceful termination")

# Register signal handlers
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


def _is_row_empty(row: Dict[str, Any], col_company: str, col_street: str, col_house_number: str, col_city: str) -> bool:
    """
    Check if a row is empty (all important fields are blank or whitespace).
    
    Args:
        row: Dictionary representing a CSV row
        col_company: Column name for company
        col_street: Column name for street
        col_house_number: Column name for house number
        col_city: Column name for city
        
    Returns:
        True if all fields are empty, False otherwise
    """
    company = str(row.get(col_company, '')).strip()
    street = str(row.get(col_street, '')).strip()
    house_number = str(row.get(col_house_number, '')).strip()
    city = str(row.get(col_city, '')).strip()
    
    # Row is empty if ALL fields are empty
    return not (company or street or house_number or city)


def run_async(coro):
    """
    Helper to run async code in celery tasks.
    Creates or reuses event loop safely.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class JobTask(Task):
    """Base task class with error handling and progress tracking."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        job_uuid = kwargs.get('job_uuid')
        if job_uuid:
            run_async(self._update_job_status(
                job_uuid,
                JobStatus.FAILED,
                error_message=str(exc)
            ))
    
    async def _update_job_status(
        self,
        job_uuid: str,
        status: JobStatus,
        force: bool = False,
        **kwargs
    ):
        """Update job status in database. Never overwrites CANCELLED or PAUSED status unless forced."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Job).where(Job.job_uuid == job_uuid)
            )
            job = result.scalar_one_or_none()
            
            if job:
                # CRITICAL: Never overwrite CANCELLED or PAUSED status (unless forced)
                # If job is CANCELLED or PAUSED, don't change it to RUNNING
                if not force and job.status in [JobStatus.CANCELLED, JobStatus.PAUSED] and status not in [JobStatus.CANCELLED, JobStatus.PAUSED]:
                    logger.warning(f"[PROTECTION] Job {job_uuid} is {job.status} - refusing to update status to {status}")
                    return  # Exit without updating
                
                job.status = status
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                
                await session.commit()
                
                # Send WebSocket notification (deferred import to avoid circular dependency)
                try:
                    from app.core.events import send_job_update
                    await send_job_update(
                        job_uuid=job_uuid,
                        update_type="status",
                        data={
                            "status": status.value,
                            "name": job.name,
                            **kwargs
                        }
                    )
                except Exception as ws_err:
                    logger.warning(f"Failed to send WebSocket notification: {ws_err}")
    
    async def _add_job_log(
        self,
        job_uuid: str,
        level: str,
        message: str,
        metadata: Dict[str, Any] = None
    ):
        """Add log entry for job."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Job).where(Job.job_uuid == job_uuid)
            )
            job = result.scalar_one_or_none()
            
            if job:
                log = JobLog(
                    job_id=job.id,
                    level=level,
                    message=message,
                    metadata=metadata or {}
                )
                session.add(log)
                await session.commit()
                
                # Send WebSocket notification for log (deferred import to avoid circular dependency)
                try:
                    from app.core.events import send_job_update
                    await send_job_update(
                        job_uuid=job_uuid,
                        update_type="log",
                        data={
                            "level": level,
                            "message": message,
                            "metadata": metadata or {},
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                except Exception as ws_err:
                    logger.warning(f"Failed to send WebSocket log notification: {ws_err}")
    
    async def _is_job_cancelled(self, job_uuid: str) -> bool:
        """Check if job has been cancelled."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Job).where(Job.job_uuid == job_uuid)
            )
            job = result.scalar_one_or_none()
            if job:
                return job.status == JobStatus.CANCELLED
            return False
    
    def _check_cancellation_sync(self, job_uuid: str) -> bool:
        """Synchronous cancellation check that can be called frequently."""
        global _termination_requested
        if _termination_requested:
            return True
        return run_async(self._is_job_cancelled(job_uuid))
    
    def _check_paused_sync(self, job_uuid: str) -> bool:
        """Synchronous pause check."""
        try:
            async def check():
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(Job).where(Job.job_uuid == job_uuid)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        return job.status == JobStatus.PAUSED
                    return False
            return run_async(check())
        except Exception as e:
            logger.error(f"Error checking pause status: {e}")
            return False


@celery_app.task(base=JobTask, bind=True, name="run_automation_job")
def run_automation_job(
    self,
    job_uuid: str,
    tool_type: str,
    input_file: str,
    output_file: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main task router for automation tools.
    
    Args:
        job_uuid: Unique job identifier
        tool_type: Type of automation tool to run (e.g., "scraply")
        input_file: Path to input CSV file
        output_file: Path to output CSV file
        config: Tool-specific configuration
        
    Returns:
        Result dictionary with statistics
    """
    if tool_type == "scraply" or tool_type == "companyinfo_scraper":  # Support both names
        return run_scraply_tool(
            job_uuid=job_uuid,
            input_file=input_file,
            output_file=output_file,
            config=config
        )
    else:
        raise ValueError(f"Unknown tool type: {tool_type}")


@celery_app.task(base=JobTask, bind=True, name="run_scraply_tool")
def run_scraply_tool(
    self,
    job_uuid: str,
    input_file: str,
    output_file: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run Scraply (CompanyInfo scraper) automation.
    
    Args:
        job_uuid: Unique job identifier
        input_file: Path to input CSV file (from scraply/csv_files/input/)
        output_file: Path to output CSV file (to scraply/csv_files/output/)
        config: Scraper configuration
        
    Returns:
        Result dictionary with statistics
    """
    global _termination_requested
    browser = None
    
    try:
        # FIRST: Check if job still exists and is not cancelled
        async def check_job_exists():
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Job).where(Job.job_uuid == job_uuid)
                )
                job = result.scalar_one_or_none()
                if not job:
                    raise ValueError(f"Job {job_uuid} not found in database - may have been deleted")
                if job.status == JobStatus.CANCELLED:
                    raise ValueError(f"Job {job_uuid} was already cancelled before task started")
                return job
        
        # Verify job exists before starting
        run_async(check_job_exists())
        
        # Update job status to RUNNING
        run_async(self._update_job_status(
            job_uuid,
            JobStatus.RUNNING,
            started_at=datetime.utcnow()
        ))
        
        # Log detailed start information
        logger.info(f"=" * 80)
        logger.info(f"[SCRAPLY TASK STARTED]")
        logger.info(f"Job UUID: {job_uuid}")
        logger.info(f"Input file (raw): {input_file}")
        logger.info(f"Output file (raw): {output_file}")
        logger.info(f"Config: {config}")
        
        # Fix path if it contains 'backend' folder (legacy path format)
        if 'backend\\scraply' in input_file or 'backend/scraply' in input_file:
            input_file = input_file.replace('backend\\scraply', 'scraply').replace('backend/scraply', 'scraply')
            logger.info(f"Corrected input file path: {input_file}")
        
        if 'backend\\scraply' in output_file or 'backend/scraply' in output_file:
            output_file = output_file.replace('backend\\scraply', 'scraply').replace('backend/scraply', 'scraply')
            logger.info(f"Corrected output file path: {output_file}")
        
        logger.info(f"=" * 80)
        
        run_async(self._add_job_log(
            job_uuid,
            "INFO",
            f"Starting Scraply - Input: {input_file}",
            {"input_file": input_file, "output_file": output_file}
        ))
        
        # HARDCODED CREDENTIALS - Working solution
        email = config.get('email') or os.environ.get('COMPANYINFO_EMAIL', '')
        password = config.get('password') or os.environ.get('COMPANYINFO_PASSWORD', '')
        headless = config.get('headless_mode', True)
        implicit_wait = config.get('implicit_wait', 5)
        page_load_timeout = config.get('page_load_timeout', 30)
        
        # Debug logging
        logger.info(f"CompanyInfo credentials - Email: {email}, Password: {'*' * len(password) if password else 'EMPTY'}")
        
        # Convert paths to Path objects
        # Paths coming in are already correct for the Docker container environment
        # The paths use forward slashes and are relative to the container filesystem
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        logger.info(f"Using input path: {input_path}")
        logger.info(f"Using output path: {output_path}")
        logger.info(f"Input path exists: {input_path.exists()}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Every upload goes through the same-file writer: the output is a COPY
        # of what was uploaded with the contact columns appended, so sheets,
        # rows and styling survive. The engine is the original CompanyInfo
        # searcher.
        return _run_legacy_tabular(self, job_uuid, input_path, output_path,
                                   config, email, password)
        
        # Read input CSV
        logger.info(f"Reading input file: {input_path}")
        run_async(self._add_job_log(job_uuid, "INFO", f"Reading {input_path}"))
        
        csv_reader = CSVReader(input_path)
        all_rows = csv_reader.read_all()
        
        # Get column mappings from config or use defaults (needed for filtering)
        col_company = config.get('col_company', scraply_config.COL_COMPANY)
        col_street = config.get('col_street', scraply_config.COL_STREET)
        col_house_number = config.get('col_house_number', scraply_config.COL_HOUSE_NUMBER)
        col_city = config.get('col_city', scraply_config.COL_CITY)
        
        # Validate column mappings exist in CSV
        if all_rows:
            csv_columns = list(all_rows[0].keys())
            logger.info(f"CSV columns found: {csv_columns}")
            logger.info(f"Column mappings - Company: '{col_company}', Street: '{col_street}', House: '{col_house_number}', City: '{col_city}'")
            
            missing_columns = []
            if col_company not in csv_columns:
                missing_columns.append(f"Business Name ('{col_company}')")
            if col_street not in csv_columns:
                missing_columns.append(f"Street Name ('{col_street}')")
            if col_house_number not in csv_columns:
                missing_columns.append(f"House Number ('{col_house_number}')")
            if col_city not in csv_columns:
                missing_columns.append(f"City ('{col_city}')")
            
            if missing_columns:
                error_msg = f"Column mapping error: The following mapped columns were not found in the CSV file: {', '.join(missing_columns)}. Available columns: {', '.join(csv_columns)}"
                logger.error(error_msg)
                run_async(self._add_job_log(job_uuid, "ERROR", error_msg))
                run_async(self._update_job_status(
                    job_uuid,
                    JobStatus.FAILED,
                    error_message=error_msg,
                    completed_at=datetime.utcnow()
                ))
                return {"error": error_msg}
        
        # Filter out empty rows
        rows = [row for row in all_rows if not _is_row_empty(row, col_company, col_street, col_house_number, col_city)]
        
        # Log if empty rows were found
        skipped_rows = len(all_rows) - len(rows)
        if skipped_rows > 0:
            logger.info(f"Skipped {skipped_rows} empty row(s)")
            run_async(self._add_job_log(job_uuid, "INFO", f"Skipped {skipped_rows} empty row(s)"))
        
        total_rows = len(rows)
        logger.info(f"Found {total_rows} rows to process")
        
        # Update job with total rows
        run_async(self._update_job_status(
            job_uuid,
            JobStatus.RUNNING,
            total_rows=total_rows
        ))
        
        if total_rows == 0:
            run_async(self._update_job_status(
                job_uuid,
                JobStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                progress=100.0
            ))
            return {"total": 0, "success": 0, "failed": 0}
        
        # Get column names from first row and add phone/email/business/owner columns (avoid duplicates)
        input_columns = list(rows[0].keys())
        output_columns = input_columns.copy()
        
        # Add output columns only if they don't already exist
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
        
        # Initialize CSV writer
        csv_writer = CSVWriter(output_path, output_columns)
        csv_writer.write_header()
        
        # Initialize browser
        logger.info("Starting browser automation")
        run_async(self._add_job_log(job_uuid, "INFO", "Initializing Chrome browser"))
        
        # In Docker, don't use Chrome profiles (they won't work)
        # Force headless mode and no profile
        profile_path = None  # Always None in Docker
        profile_name = 'Default'
        
        # Create browser (not using context manager for better control)
        browser = BrowserAutomation(
            profile_path=profile_path,
            profile_name=profile_name,
            headless=True,  # Always headless in Docker
            implicit_wait=implicit_wait
        )
        browser.__enter__()  # Manually call context manager enter
        
        try:
            # Initialize searcher
            searcher = CompanyInfoSearcher(
                browser=browser,
                base_url='https://company.info',
                timeout=page_load_timeout,
                email=email,
                password=password
            )
            
            # PARALLEL PROCESSING CONFIG (Set to 1 to disable parallelization)
            NUM_WORKERS = 3  # Change to 1 to go back to sequential processing
            ENABLE_ANTI_DETECTION = True  # Random delays between requests
            
            if NUM_WORKERS > 1:
                logger.info(f"🚀 Starting PARALLEL processing with {NUM_WORKERS} workers")
                parallel_result = _process_parallel(
                    task_instance=self,
                    job_uuid=job_uuid,
                    rows=rows,
                    total_rows=total_rows,
                    col_company=col_company,
                    col_street=col_street,
                    col_house_number=col_house_number,
                    col_city=col_city,
                    email=email,
                    password=password,
                    headless=headless,
                    implicit_wait=implicit_wait,
                    page_load_timeout=page_load_timeout,
                    output_path=output_path,
                    csv_writer=csv_writer,
                    num_workers=NUM_WORKERS,
                    enable_anti_detection=ENABLE_ANTI_DETECTION
                )
                
                # Handle parallel processing result
                result_status = parallel_result.get("status", "completed")
                
                if result_status == "cancelled":
                    logger.info(f"Job {job_uuid} was cancelled during parallel processing")
                    # Job status already set to CANCELLED in _process_parallel
                    run_async(self._add_job_log(
                        job_uuid,
                        "WARNING",
                        f"Job cancelled - Processed: {parallel_result.get('processed', 0)}, Successful: {parallel_result.get('successful', 0)}, Failed: {parallel_result.get('failed', 0)}"
                    ))
                else:
                    # Job completed - set final status
                    success_rate = (parallel_result.get('successful', 0) / total_rows * 100) if total_rows > 0 else 0
                    
                    run_async(self._update_job_status(
                        job_uuid,
                        JobStatus.COMPLETED,
                        progress=100.0,
                        completed_at=datetime.utcnow(),
                        processed_rows=parallel_result.get('processed', total_rows),
                        successful_rows=parallel_result.get('successful', 0),
                        failed_rows=parallel_result.get('failed', 0),
                        output_file_path=str(output_file)
                    ))
                    
                    run_async(self._add_job_log(
                        job_uuid,
                        "INFO",
                        f"Job completed: {parallel_result.get('successful', 0)}/{total_rows} successful ({success_rate:.1f}%)",
                        parallel_result
                    ))
                
                return parallel_result
            
            # SEQUENTIAL PROCESSING (Original code)
            logger.info("Starting sequential processing (1 worker)")
            successful = 0
            failed = 0
            
            # Batch update tracking
            last_db_update_idx = 0
            last_notification_progress = 0.0
            BATCH_SIZE = 50  # Update DB every 50 rows
            NOTIFICATION_THRESHOLD = 5.0  # Send WebSocket every 5% progress
            
            # Column mappings already retrieved above for filtering
            for idx, row in enumerate(rows, 1):
                # Check if job has been cancelled or terminated BEFORE processing each row
                if _termination_requested or run_async(self._is_job_cancelled(job_uuid)):
                    logger.warning(f"Job {job_uuid} was cancelled/terminated at row {idx}/{total_rows}")
                    run_async(self._add_job_log(
                        job_uuid,
                        "WARNING",
                        f"Job cancelled/terminated by user at row {idx}/{total_rows}"
                    ))
                    
                    # Mark as cancelled if not already
                    if _termination_requested:
                        run_async(self._update_job_status(
                            job_uuid,
                            JobStatus.CANCELLED,
                            completed_at=datetime.utcnow()
                        ))
                    
                    # Exit task (browser will be closed in finally block)
                    return {
                        "total": total_rows,
                        "processed": idx - 1,
                        "successful": successful,
                        "failed": failed,
                        "status": "cancelled"
                    }
                
                try:
                    # Extract company info
                    company_name = row.get(col_company, '').strip()
                    street = row.get(col_street, '').strip()
                    house_number = row.get(col_house_number, '').strip()
                    city = row.get(col_city, '').strip()
                    
                    logger.info(f"[{idx}/{total_rows}] Processing: {company_name}")
                    
                    # Check cancellation before heavy operation
                    if self._check_cancellation_sync(job_uuid):
                        logger.warning(f"Job {job_uuid} cancelled mid-row at {idx}/{total_rows}")
                        raise Terminated("Job cancelled by user")
                    
                    # Check if paused - wait until resumed or cancelled
                    while self._check_paused_sync(job_uuid):
                        logger.info(f"Job {job_uuid} is paused, waiting...")
                        time.sleep(2)
                        # Check if cancelled while paused
                        if self._check_cancellation_sync(job_uuid):
                            logger.warning(f"Job {job_uuid} cancelled while paused")
                            raise Terminated("Job cancelled while paused")
                    
                    # Search and extract
                    contact_info = searcher.search_company(
                        company_name=company_name,
                        street=street,
                        house_number=house_number,
                        city=city
                    )
                    
                    # Anti-detection: Random delay between requests (disabled in sequential mode)
                    # Uncomment to enable: time.sleep(random.uniform(8, 20))
                    
                    # Check if company should be skipped (too many businesses - rich owner)
                    if contact_info.get('skip'):
                        logger.info(f"[SKIPPED] {contact_info.get('reason', 'Unknown reason')}")
                        # Write to output with NULL values
                        for i in range(1, 6):
                            row[f'NUMBER {i}'] = 'NULL'
                        row['EMAIL'] = 'NULL'
                        row['BUSINESS_NAME'] = 'NULL'
                        row['OWNER_NAME'] = 'NULL'
                        row['NOTE'] = contact_info.get('note', 'SKIPPED: Too many businesses')
                        csv_writer.append_row(row)
                        
                        # Count as failed (skipped is not success)
                        failed += 1
                    else:
                        # Get phone list (06 number will be first if found)
                        phones = contact_info.get('phones', [])
                        
                        # Populate NUMBER 1, NUMBER 2, NUMBER 3, etc. columns
                        for i in range(1, 6):
                            col_name = f'NUMBER {i}'
                            if i <= len(phones):
                                row[col_name] = phones[i-1]  # 06 number goes in NUMBER 1
                            else:
                                row[col_name] = 'NULL'  # NULL if no more numbers
                        
                        # Add other results to row (use NULL for empty values)
                        row['EMAIL'] = contact_info.get('email', '') or 'NULL'
                        row['BUSINESS_NAME'] = contact_info.get('business', '') or 'NULL'
                        row['OWNER_NAME'] = contact_info.get('owner', '') or 'NULL'
                        row['NOTE'] = contact_info.get('note', '') or 'NULL'
                        
                        # Write to output
                        csv_writer.append_row(row)
                        
                        if phones or contact_info.get('email'):
                            successful += 1
                            phones_str = ', '.join(phones) if phones else 'N/A'
                            logger.info(f"[SUCCESS] Phones: {phones_str}, Email: {contact_info.get('email', 'N/A')}, Business: {contact_info.get('business', 'N/A')}, Owner: {contact_info.get('owner', 'N/A')}")
                        else:
                            failed += 1
                            logger.warning("[NOT FOUND] No contact info found")
                    
                    # Calculate progress
                    progress = (idx / total_rows) * 100
                    
                    # Batch database updates - only update every BATCH_SIZE rows or at end
                    should_update_db = (
                        idx - last_db_update_idx >= BATCH_SIZE or  # Every 50 rows
                        idx == total_rows or  # Last row
                        idx % 100 == 0  # Also every 100 for safety
                    )
                    
                    if should_update_db:
                        run_async(self._update_job_status(
                            job_uuid,
                            JobStatus.RUNNING,
                            progress=progress,
                            processed_rows=idx,
                            successful_rows=successful,
                            failed_rows=failed
                        ))
                        last_db_update_idx = idx
                        
                        # Check cancellation only during DB updates (not every row)
                        if run_async(self._is_job_cancelled(job_uuid)):
                            logger.warning(f"Job {job_uuid} detected as CANCELLED after row {idx}")
                            raise Terminated("Job was cancelled during execution")
                    
                    # Throttled WebSocket notifications - only send at 5% intervals
                    progress_delta = progress - last_notification_progress
                    should_send_notification = (
                        progress_delta >= NOTIFICATION_THRESHOLD or  # Every 5% progress
                        idx == total_rows or  # Last row
                        idx % 100 == 0  # Also every 100 rows
                    )
                    
                    # Log progress every 100 rows (reduced from 10)
                    if idx % 100 == 0:
                        run_async(self._add_job_log(
                            job_uuid,
                            "INFO",
                            f"Progress: {idx}/{total_rows} ({progress:.1f}%)",
                            {"successful": successful, "failed": failed}
                        ))
                        last_notification_progress = progress
                
                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing row {idx}: {e}")
                    
                    # Write row with NULL values for contact fields
                    for i in range(1, 6):
                        row[f'NUMBER {i}'] = 'NULL' if i == 1 else ''
                    row['EMAIL'] = 'NULL'
                    row['BUSINESS_NAME'] = 'NULL'
                    row['OWNER_NAME'] = 'NULL'
                    row['NOTE'] = f'ERROR: {str(e)[:100]}'
                    csv_writer.append_row(row)
                    
                    run_async(self._add_job_log(
                        job_uuid,
                        "ERROR",
                        f"Failed to process row {idx}: {str(e)}"
                    ))
            
            logger.info(f"Output file saved: {output_file}")
            
            # Job completed
            success_rate = (successful / total_rows * 100) if total_rows > 0 else 0
            
            run_async(self._update_job_status(
                job_uuid,
                JobStatus.COMPLETED,
                progress=100.0,
                completed_at=datetime.utcnow(),
                processed_rows=total_rows,
                successful_rows=successful,
                failed_rows=failed,
                output_file_path=str(output_file)
            ))
            
            run_async(self._add_job_log(
                job_uuid,
                "INFO",
                f"Job completed: {successful}/{total_rows} successful ({success_rate:.1f}%)",
                {
                    "total": total_rows,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": success_rate
                }
            ))
            
            return {
                "total": total_rows,
                "success": successful,
                "failed": failed,
                "success_rate": success_rate
            }
        
        finally:
            # Always close browser when exiting this try block
            try:
                if browser is not None:
                    browser.__exit__(None, None, None)  # Manually call context manager exit
                    logger.info("Browser closed successfully")
            except Exception as cleanup_err:
                logger.warning(f"Failed to close browser during cleanup: {cleanup_err}")
    
    except (SoftTimeLimitExceeded, Terminated) as e:
        # Task was terminated by Celery (e.g., via revoke)
        logger.warning(f"Task {job_uuid} terminated: {e}")
        
        # Mark job as cancelled
        run_async(self._update_job_status(
            job_uuid,
            JobStatus.CANCELLED,
            completed_at=datetime.utcnow()
        ))
        
        run_async(self._add_job_log(
            job_uuid,
            "WARNING",
            "Task terminated by system"
        ))
        
        # Browser cleanup is handled in finally block
        return {
            "status": "terminated",
            "message": str(e)
        }
        
    except Exception as e:
        logger.error(f"Fatal error in job {job_uuid}: {e}", exc_info=True)
        
        run_async(self._update_job_status(
            job_uuid,
            JobStatus.FAILED,
            error_message=str(e),
            completed_at=datetime.utcnow()
        ))
        
        run_async(self._add_job_log(
            job_uuid,
            "CRITICAL",
            f"Job failed: {str(e)}"
        ))
        
        raise
    
    finally:
        # Reset termination flag for next task
        _termination_requested = False


def _run_legacy_tabular(task, job_uuid: str, input_path, output_path,
                        config: Dict[str, Any], email: str, password: str) -> Dict[str, Any]:
    """
    Run the original CompanyInfo searcher over a CSV or Excel upload and return
    the SAME file with the contact columns appended.

    The column mapping comes from the job config (what the user confirmed in the
    mapping screen). Anything the user left blank falls back to auto-detection,
    so a file still runs if the mapping step was skipped.
    """
    import random
    from pathlib import Path as _Path

    from src.modules.browser_automation import BrowserAutomation
    from src.modules.companyinfo_searcher import CompanyInfoSearcher
    from src.modules.kadaster_map import detect_any
    from src.modules.tabular_io import TabularFile

    OUT_COLS = ['NUMBER 1', 'NUMBER 2', 'NUMBER 3', 'NUMBER 4', 'NUMBER 5',
                'EMAIL', 'BUSINESS_NAME', 'OWNER_NAME', 'NOTE']

    # --- where the data is, and which columns to use -----------------------
    try:
        det = detect_any(input_path)
    except Exception as e:
        logger.warning(f"[LEGACY] detection failed ({e}); assuming header row 1")
        det = {'sheet': None, 'header_row': 1, 'fields': {}, 'file_type': 'csv'}

    sheet = config.get('sheet') or det.get('sheet')
    header_row = int(config.get('header_row') or det.get('header_row') or 1)
    f = det.get('fields', {})
    col_company = config.get('col_company') or f.get('company', '')
    col_prefix = config.get('col_name_prefix') or f.get('name_prefix', '')
    col_street = config.get('col_street') or f.get('street', '')
    col_house = config.get('col_house_number') or f.get('house_number', '')
    col_city = config.get('col_city') or f.get('city', '')

    logger.info(f"[LEGACY] sheet={sheet!r} header_row={header_row} "
                f"company={col_company!r} street={col_street!r} "
                f"house={col_house!r} city={col_city!r}")
    run_async(task._add_job_log(
        job_uuid, "INFO",
        f"Using columns - name: '{col_company}', street: '{col_street}', "
        f"house: '{col_house}', city: '{col_city}'"
        + (f" (sheet '{sheet}', header row {header_row})" if sheet else "")))

    tf = TabularFile(input_path, sheet=sheet, header_row=header_row)
    rows = [r for r in tf.read_rows() if not TabularFile.is_blank(r)]
    if not col_company and not col_street:
        msg = ("Column mapping error: no name or street column was given and "
               "none could be detected. Available columns: "
               + ", ".join([h for h in tf.headers if h][:40]))
        run_async(task._update_job_status(job_uuid, JobStatus.FAILED,
                                          error_message=msg,
                                          completed_at=datetime.utcnow()))
        run_async(task._add_job_log(job_uuid, "ERROR", msg))
        return {"error": msg}

    total = len(rows)
    run_async(task._update_job_status(job_uuid, JobStatus.RUNNING, total_rows=total,
                                      processed_rows=0, successful_rows=0, failed_rows=0))
    if total == 0:
        run_async(task._update_job_status(job_uuid, JobStatus.COMPLETED, progress=100.0,
                                          completed_at=datetime.utcnow()))
        return {"total": 0, "success": 0, "failed": 0}

    def _new_browser():
        """Chrome can fail to start for a moment - retry before giving up."""
        for attempt in (1, 2, 3):
            try:
                b = BrowserAutomation(profile_path=None, profile_name='SCRAPLY',
                                      headless=True, implicit_wait=5)
                b.__enter__()
                se = CompanyInfoSearcher(browser=b, base_url='https://company.info',
                                         timeout=int(config.get('page_load_timeout', 30)),
                                         email=email, password=password)
                return b, se
            except Exception as e:
                logger.error(f"[LEGACY] browser start failed ({attempt}/3): {e}")
                time.sleep(15 * attempt)
        return None, None

    browser, searcher = _new_browser()
    if not searcher:
        msg = "Browser could not be started"
        run_async(task._update_job_status(job_uuid, JobStatus.FAILED, error_message=msg,
                                          completed_at=datetime.utcnow()))
        return {"error": msg}

    results: Dict[int, Dict[str, Any]] = {}
    found = empty = 0
    min_delay = float(config.get('min_delay', 1.0))
    max_delay = float(config.get('max_delay', 3.0))
    recycle_every = int(config.get('recycle_every', 40))
    since_recycle = 0
    cancelled = False

    try:
        for n, row in enumerate(rows, 1):
            if _termination_requested or task._check_cancellation_sync(job_uuid):
                cancelled = True
                logger.warning(f"[LEGACY] cancelled at row {n}/{total}")
                break
            while task._check_paused_sync(job_uuid):
                time.sleep(2)
                if task._check_cancellation_sync(job_uuid):
                    cancelled = True
                    break
            if cancelled:
                break

            get = lambda c: (row.get(c) or '').strip() if c else ''
            name = f"{get(col_prefix)} {get(col_company)}".strip()
            street, house, city = get(col_street), get(col_house), get(col_city)
            if not name and not street:
                results[row['row_index']] = {}
                empty += 1
                continue

            if since_recycle >= recycle_every:
                try:
                    browser.__exit__(None, None, None)
                except Exception:
                    pass
                time.sleep(2)
                browser, searcher = _new_browser()
                since_recycle = 0
                if not searcher:
                    break

            try:
                info = searcher.search_company(company_name=name, street=street,
                                               house_number=house, city=city)
            except Exception as e:
                logger.error(f"[LEGACY] row {n} failed: {e}")
                try:
                    browser.__exit__(None, None, None)
                except Exception:
                    pass
                time.sleep(3)
                browser, searcher = _new_browser()
                since_recycle = 0
                if not searcher:
                    break
                try:
                    info = searcher.search_company(company_name=name, street=street,
                                                   house_number=house, city=city)
                except Exception as e2:
                    info = {'phones': [], 'email': '', 'business': '', 'owner': '',
                            'note': f'ERROR: {str(e2)[:80]}'}

            if info.get('skip'):
                cols = {'NOTE': info.get('note') or 'SKIPPED: Too many businesses'}
            else:
                phones = info.get('phones') or []
                cols = {f'NUMBER {i}': (phones[i - 1] if i <= len(phones) else '')
                        for i in range(1, 6)}
                cols['EMAIL'] = info.get('email') or ''
                cols['BUSINESS_NAME'] = info.get('business') or ''
                cols['OWNER_NAME'] = info.get('owner') or ''
                cols['NOTE'] = info.get('note') or ''
            results[row['row_index']] = cols
            if cols.get('NUMBER 1') or cols.get('EMAIL'):
                found += 1
            else:
                empty += 1
            since_recycle += 1

            run_async(task._update_job_status(
                job_uuid, JobStatus.RUNNING,
                progress=round(n / total * 100, 1),
                processed_rows=n, successful_rows=found, failed_rows=empty))
            if n % 25 == 0:
                run_async(task._add_job_log(
                    job_uuid, "INFO", f"Progress: {n}/{total} - {found} with contact"))
            time.sleep(random.uniform(min_delay, max_delay))
    finally:
        try:
            if browser is not None:
                browser.__exit__(None, None, None)
        except Exception:
            pass

    # Deliverables always go out as Excel, whatever was uploaded. A CSV result
    # loses the leading zero on every 06... phone number and rounds 16-digit BAG
    # ids the moment anyone opens it in Excel, which is where these files are
    # read. An .xlsx upload still keeps its own sheets, styling and formats.
    out = _Path(output_path).with_suffix('.xlsx')
    filled = tf.write_output(out, OUT_COLS, results)
    logger.info(f"[LEGACY] wrote {out} ({filled} rows populated)")

    processed = found + empty
    run_async(task._update_job_status(
        job_uuid,
        JobStatus.CANCELLED if cancelled else JobStatus.COMPLETED,
        progress=round(processed / total * 100, 1) if cancelled else 100.0,
        completed_at=datetime.utcnow(),
        processed_rows=processed, successful_rows=found, failed_rows=empty,
        output_file_path=str(out)))
    run_async(task._add_job_log(
        job_uuid, "INFO",
        f"{'Cancelled' if cancelled else 'Completed'}: {found} with contact, "
        f"{empty} without, of {processed} processed"))
    return {"total": total, "success": found, "failed": empty,
            "output_file": str(out), "cancelled": cancelled}

def _process_parallel(
    task_instance,
    job_uuid: str,
        rows: list,
        total_rows: int,
        col_company: str,
        col_street: str,
        col_house_number: str,
        col_city: str,
        email: str,
        password: str,
        headless: bool,
        implicit_wait: int,
        page_load_timeout: int,
        output_path: str,
        csv_writer,
        num_workers: int = 2,
        enable_anti_detection: bool = True
    ):
        """
        Process rows in parallel with multiple workers.
        Includes cancellation support, browser recycling, and crash recovery.
        
        Args:
            job_uuid: Job UUID
            rows: List of all rows to process
            total_rows: Total row count
            col_company, col_street, col_house_number, col_city: Column mappings
            email, password: CompanyInfo credentials
            headless: Headless mode flag
            implicit_wait, page_load_timeout: Browser timeouts
            output_path: Output CSV path
            csv_writer:CSV writer instance
            num_workers: Number of parallel workers (default: 2)
            enable_anti_detection: Enable random delays (default: True)
            
        Returns:
            Dict with results
        """
        from .parallel_worker import (
            process_chunk_worker,
            ParallelProgress,
            ThreadSafeCSVWriter,
            CancellationToken
        )
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        logger.info(f"🚀 PARALLEL MODE: Splitting {total_rows} rows across {num_workers} workers")
        
        # Create shared cancellation token for all workers
        cancellation_token = CancellationToken()
        
        # Split rows into chunks
        chunk_size = total_rows // num_workers
        chunks = []
        chunk_start_indices = []
        
        for i in range(num_workers):
            start_idx = i * chunk_size
            # Last worker gets remaining rows
            end_idx = start_idx + chunk_size if i < num_workers - 1 else total_rows
            chunks.append(rows[start_idx:end_idx])
            chunk_start_indices.append(start_idx)
            logger.info(f"📦 Worker {i+1}: Rows {start_idx+1} to {end_idx} ({end_idx - start_idx} rows)")
        
        # Thread-safe progress tracking
        progress_tracker = ParallelProgress()
        thread_safe_csv = ThreadSafeCSVWriter(csv_writer)
        
        # Track DB update intervals
        last_db_update_count = 0
        BATCH_SIZE = 50
        
        # Track if job was cancelled
        job_was_cancelled = False
        
        # Submit worker tasks
        workers_started_at = datetime.utcnow()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all worker tasks
            futures = []
            for worker_id in range(1, num_workers + 1):
                chunk_idx = worker_id - 1
                future = executor.submit(
                    process_chunk_worker,
                    worker_id=worker_id,
                    chunk=chunks[chunk_idx],
                    chunk_start_idx=chunk_start_indices[chunk_idx],
                    total_rows=total_rows,
                    email=email,
                    password=password,
                    headless=headless,
                    implicit_wait=implicit_wait,
                    page_load_timeout=page_load_timeout,
                    col_company=col_company,
                    col_street=col_street,
                    col_house_number=col_house_number,
                    col_city=col_city,
                    csv_writer=thread_safe_csv,
                    progress_tracker=progress_tracker,
                    enable_anti_detection=enable_anti_detection,
                    cancellation_token=cancellation_token
                )
                futures.append((worker_id, future))
            
            logger.info(f"✅ All {num_workers} workers started")
            
            # Monitor progress while workers run
            completed_workers = 0
            logger.info("🔍 Starting progress monitoring loop...")
            try:
                while completed_workers < num_workers:
                    time.sleep(2)  # Check every 2 seconds for faster cancellation response
                    
                    # CHECK FOR CANCELLATION in monitoring loop
                    if run_async(task_instance._is_job_cancelled(job_uuid)):
                        logger.warning(f"🛑 Job {job_uuid} CANCELLED - signaling all workers to stop")
                        cancellation_token.cancel()  # Signal all workers to stop
                        job_was_cancelled = True
                        
                        # Give workers a moment to notice cancellation
                        time.sleep(2)
                        
                        # Update job status
                        run_async(task_instance._update_job_status(
                            job_uuid,
                            JobStatus.CANCELLED,
                            completed_at=datetime.utcnow()
                        ))
                        
                        run_async(task_instance._add_job_log(
                            job_uuid,
                            "WARNING",
                            "Job cancelled by user - all workers stopped"
                        ))
                        
                        # Break out of monitoring loop immediately
                        break
                    
                    # Get current stats
                    stats = progress_tracker.get_stats()
                    processed = stats["processed"]
                    successful = stats["successful"]
                    failed = stats["failed"]
                    progress = (processed / total_rows * 100) if total_rows > 0 else 0
                    
                    logger.info(f"🔍 Monitoring: processed={processed}, successful={successful}, failed={failed}, progress={progress:.1f}%")
                    
                    # ALWAYS update UI (every 5 sec check) - workers run in separate threads, no performance impact
                    try:
                        run_async(task_instance._update_job_status(
                            job_uuid,
                            JobStatus.RUNNING,
                            progress=progress,
                            processed_rows=processed,
                            successful_rows=successful,
                            failed_rows=failed
                        ))
                    except Exception as update_err:
                        logger.error(f"❌ Failed to update job status: {update_err}")
                    
                    # Log only on significant progress (batch threshold)
                    if processed - last_db_update_count >= BATCH_SIZE:
                        logger.info(f"📊 Progress: {processed}/{total_rows} ({progress:.1f}%) - ✅{successful} ❌{failed}")
                        last_db_update_count = processed
                    
                    # Check if any workers completed
                    completed_workers = sum(1 for _, f in futures if f.done())
                    
            except Exception as monitor_err:
                logger.error(f"❌ Monitoring loop error: {monitor_err}", exc_info=True)
            
            # If cancelled, signal again to ensure all workers stop
            if job_was_cancelled:
                cancellation_token.cancel()
            
            # Collect results from all workers (with short timeout if cancelled)
            timeout_per_worker = 5 if job_was_cancelled else 30
            worker_results = []
            for worker_id, future in futures:
                try:
                    result = future.result(timeout=timeout_per_worker)
                    worker_results.append(result)
                    logger.info(f"🤖 Worker {worker_id}: {result}")
                except Exception as e:
                    logger.error(f"🤖 Worker {worker_id}: Failed to get result - {e}")
                    worker_results.append({
                        "worker_id": worker_id,
                        "status": "error" if not job_was_cancelled else "cancelled",
                        "error": str(e)
                    })
        
        # Final stats
        final_stats = progress_tracker.get_stats()
        total_successful = final_stats["successful"]
        total_failed = final_stats["failed"]
        total_processed = final_stats["processed"]
        
        logger.info(f"🏁 PARALLEL PROCESSING {'CANCELLED' if job_was_cancelled else 'COMPLETED'}:")
        logger.info(f"   📊 Total Processed: {total_processed}/{total_rows}")
        logger.info(f"   ✅ Successful: {total_successful}")
        logger.info(f"   ❌ Failed: {total_failed}")
        logger.info(f"   ⏱️ Worker Results: {worker_results}")
        
        # Final DB update - don't overwrite CANCELLED status
        if job_was_cancelled:
            run_async(task_instance._update_job_status(
                job_uuid,
                JobStatus.CANCELLED,
                force=True,  # Force update even if already cancelled
                progress=(total_processed / total_rows * 100) if total_rows > 0 else 0,
                processed_rows=total_processed,
                successful_rows=total_successful,
                failed_rows=total_failed,
                completed_at=datetime.utcnow()
            ))
        else:
            run_async(task_instance._update_job_status(
                job_uuid,
                JobStatus.RUNNING,
                progress=100.0,
                processed_rows=total_processed,
                successful_rows=total_successful,
                failed_rows=total_failed
            ))
        
        return {
            "total": total_rows,
            "processed": total_processed,
            "successful": total_successful,
            "failed": total_failed,
            "workers": worker_results,
            "mode": "parallel",
            "status": "cancelled" if job_was_cancelled else "completed"
        }
