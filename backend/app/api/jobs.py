"""
Job management routes
"""
import uuid
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..db.models import Job, JobStatus, JobLog, ToolType
from ..core.config import settings
from ..schemas.schemas import (
    JobCreate,
    JobResponse,
    JobListResponse,
    JobLogResponse,
    JobUpdate
)
from ..core.security import get_current_user
from ..tasks.automation_tasks import run_automation_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new automation job.
    
    Note: This creates the job record but doesn't start it.
    Use POST /jobs/{job_id}/start to begin execution.
    
    Args:
        job_data: Job creation data
        user_id: Current user ID
        db: Database session
        
    Returns:
        Created job object
    """
    job = Job(
        user_id=int(user_id),
        job_uuid=str(uuid.uuid4()),
        tool_type=job_data.tool_type,
        name=job_data.name,
        description=job_data.description,
        priority=job_data.priority,
        config=job_data.config or {},
        status=JobStatus.PENDING
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status_filter: Optional[JobStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all jobs for current user with pagination.
    
    Args:
        status_filter: Filter by job status
        page: Page number (1-indexed)
        page_size: Items per page
        user_id: Current user ID
        db: Database session
        
    Returns:
        Paginated list of jobs
    """
    # Shared dashboard: all users see all jobs
    query = select(Job)
    
    if status_filter:
        query = query.where(Job.status == status_filter)
    
    query = query.order_by(desc(Job.created_at))
    
    # Get total count
    count_query = select(func.count()).select_from(query.alias())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/{job_uuid}", response_model=JobResponse)
async def get_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get specific job details.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        Job object
        
    Raises:
        HTTPException: If job not found or unauthorized
    """
    # Shared dashboard: any user can view any job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.patch("/{job_uuid}", response_model=JobResponse)
async def update_job(
    job_uuid: str,
    job_update: JobUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update job details (only for pending jobs).
    
    Args:
        job_uuid: Job UUID
        job_update: Fields to update
        user_id: Current user ID
        db: Database session
        
    Returns:
        Updated job object
        
    Raises:
        HTTPException: If job not found or not in pending status
    """
    # Shared dashboard: any user can update any pending/failed job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in [JobStatus.PENDING, JobStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update pending or failed jobs"
        )
    
    # Update fields
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)
    
    await db.commit()
    await db.refresh(job)
    
    return job


@router.post("/{job_uuid}/start", response_model=JobResponse)
async def start_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start job execution.
    
    This queues the job for processing by Celery workers.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        Updated job object with QUEUED status
        
    Raises:
        HTTPException: If job not found, missing files, or already running
    """
    # Shared dashboard: any user can start any job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in [JobStatus.PENDING, JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start job with status: {job.status}"
        )
    
    if not job.input_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No input file uploaded for this job"
        )
    
    # Debug logging
    logger.info(f"[START JOB] Job UUID: {job_uuid}")
    logger.info(f"[START JOB] Input file: {job.input_file_path}")
    logger.info(f"[START JOB] Output file: {job.output_file_path}")
    
    # Clean up any orphaned tasks before starting new job
    # This prevents stuck jobs from blocking the queue
    logger.info(f"[START JOB] Checking for orphaned running/queued jobs...")
    orphaned_result = await db.execute(
        select(Job).where(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]),
            Job.job_uuid != job_uuid  # Not the current job
        )
    )
    orphaned_jobs = orphaned_result.scalars().all()
    
    if orphaned_jobs:
        logger.warning(f"[START JOB] Found {len(orphaned_jobs)} orphaned running/queued jobs - will revoke their tasks")
        from ..core.celery_app import celery_app
        from celery.result import AsyncResult
        
        for orphaned_job in orphaned_jobs:
            try:
                logger.info(f"[START JOB] Revoking orphaned task {orphaned_job.celery_task_id} for job {orphaned_job.job_uuid}")
                if orphaned_job.celery_task_id:
                    celery_app.control.revoke(orphaned_job.celery_task_id, terminate=True, signal='SIGTERM')
                    AsyncResult(orphaned_job.celery_task_id, app=celery_app).revoke(terminate=True)
                
                # Mark as cancelled
                orphaned_job.status = JobStatus.CANCELLED
                orphaned_job.completed_at = datetime.utcnow()
            except Exception as e:
                logger.error(f"[START JOB] Failed to revoke orphaned task: {e}")
        
        await db.commit()
        logger.info(f"[START JOB] Cleaned up {len(orphaned_jobs)} orphaned jobs")
    
    # Queue the job with credentials from environment variables
    import os
    
    # Debug: check if env vars exist
    logger.info(f"[API DEBUG] All COMPANYINFO vars: {[k for k in os.environ.keys() if 'COMPANYINFO' in k]}")
    email_val = os.environ.get('COMPANYINFO_EMAIL', 'FALLBACK_EMAIL')
    pass_val = os.environ.get('COMPANYINFO_PASSWORD', 'FALLBACK_PASS')
    logger.info(f"[API DEBUG] email_val={email_val}, pass_val={pass_val[:5] if pass_val and pass_val != 'FALLBACK_PASS' else pass_val}...")
    
    job_config = job.config or {}
    logger.info(f"[API DEBUG] job.config initial value: {job.config}")
    logger.info(f"[API DEBUG] job_config before assignment: {job_config}")
    
    # Add credentials from environment variables if not in config OR if empty
    if not job_config.get('email'):
        job_config['email'] = email_val
    if not job_config.get('password'):
        job_config['password'] = pass_val
    
    logger.info(f"[API DEBUG] job_config after assignment: email={job_config.get('email')}, password={job_config.get('password', '')[:5]}...")
    logger.info(f"[API] Sending to Celery - Email: {job_config.get('email')}, Password: {'*' * len(job_config.get('password', '')) if job_config.get('password') else 'EMPTY'}")
    
    task = run_automation_job.apply_async(
        kwargs={
            "job_uuid": job_uuid,
            "tool_type": job.tool_type.value,
            "input_file": job.input_file_path,
            "output_file": job.output_file_path or job.input_file_path.replace('input', 'output').replace('.csv', '_DONE.csv'),
            "config": job_config
        },
        priority=_get_celery_priority(job.priority)
    )
    
    # Update job
    job.status = JobStatus.QUEUED
    job.celery_task_id = task.id
    
    await db.commit()
    await db.refresh(job)
    
    return job


@router.post("/{job_uuid}/cancel", response_model=JobResponse)
async def cancel_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running job.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        Updated job object with CANCELLED status
        
    Raises:
        HTTPException: If job not found or cannot be cancelled
    """
    # Shared dashboard: any user can cancel any job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    logger.info(f"[CANCEL] Cancelling job {job_uuid} with task ID: {job.celery_task_id}")
    logger.info(f"[CANCEL] Current status: {job.status}")
    
    # FIRST: Mark job as cancelled in database IMMEDIATELY
    # This stops the task loop from continuing
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"[CANCEL] Job {job_uuid} marked as CANCELLED in database")
    
    # SECOND: Revoke Celery task with terminate
    if job.celery_task_id:
        from ..core.celery_app import celery_app
        try:
            logger.info(f"[CANCEL] Attempting to revoke task {job.celery_task_id}")
            
            # Method 1: Control revoke with terminate (sends SIGTERM to worker)
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal='SIGTERM')
            logger.info(f"[CANCEL] Sent SIGTERM via control.revoke for task {job.celery_task_id}")
            
            # Method 2: AsyncResult revoke (marks task as revoked in Redis)
            from celery.result import AsyncResult
            task_result = AsyncResult(job.celery_task_id, app=celery_app)
            task_result.revoke(terminate=True, signal='SIGTERM')
            logger.info(f"[CANCEL] Marked task {job.celery_task_id} as revoked in Redis")
            
            # Method 3: Force kill if still running after 2 seconds
            import asyncio
            await asyncio.sleep(2)
            celery_app.control.revoke(job.celery_task_id, terminate=True, signal='SIGKILL')
            logger.info(f"[CANCEL] Sent SIGKILL as fallback for task {job.celery_task_id}")
                
        except Exception as e:
            logger.error(f"[CANCEL] Failed to terminate task: {e}", exc_info=True)
    else:
        logger.warning(f"[CANCEL] No celery_task_id found for job {job_uuid}")
    
    logger.info(f"[CANCEL] Job {job_uuid} cancel complete - CANCELLED in DB, task revoked")
    
    return job


@router.post("/{job_uuid}/pause", response_model=JobResponse)
async def pause_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pause a running job.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        Updated job
    """
    # Shared dashboard: any user can pause any job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Allow pausing RUNNING or RETRYING jobs
    if job.status not in [JobStatus.RUNNING, JobStatus.RETRYING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause job with status: {job.status}"
        )
    
    # Mark job as paused
    job.status = JobStatus.PAUSED
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"[PAUSE] Job {job_uuid} paused")
    
    return job


@router.post("/{job_uuid}/resume", response_model=JobResponse)
async def resume_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Resume a paused job.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        Updated job
    """
    # Shared dashboard: any user can resume any job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status != JobStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume job with status: {job.status}"
        )
    
    # Mark job as running again
    job.status = JobStatus.RUNNING
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"[RESUME] Job {job_uuid} resumed")
    
    return job


@router.post("/{job_uuid}/retry", response_model=JobResponse)
async def retry_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retry a failed or cancelled job from where it stopped.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        Updated job
    """
    # Shared dashboard: any user can retry any job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job with status: {job.status}. Only FAILED or CANCELLED jobs can be retried."
        )
    
    # Mark job as retrying and queue it
    job.status = JobStatus.RETRYING
    job.completed_at = None
    await db.commit()
    await db.refresh(job)

    # Re-queue the Celery task with same parameters as start_job
    from ..tasks.automation_tasks import run_automation_job
    import os
    job_config = job.config or {}
    if not job_config.get('email'):
        job_config['email'] = os.environ.get('COMPANYINFO_EMAIL', '')
    if not job_config.get('password'):
        job_config['password'] = os.environ.get('COMPANYINFO_PASSWORD', '')

    task = run_automation_job.apply_async(
        kwargs={
            "job_uuid": job_uuid,
            "tool_type": job.tool_type.value,
            "input_file": job.input_file_path,
            "output_file": job.output_file_path,
            "config": job_config
        },
        priority=_get_celery_priority(job.priority)
    )

    job.celery_task_id = task.id
    job.status = JobStatus.QUEUED
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"[RETRY] Job {job_uuid} requeued with task ID: {task.id}")
    
    return job


@router.delete("/{job_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a job and its logs.
    
    Only completed, failed, or cancelled jobs can be deleted.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Raises:
        HTTPException: If job not found or cannot be deleted
    """
    # Shared dashboard: any user can delete any completed/failed job
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status in [JobStatus.RUNNING, JobStatus.QUEUED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete running or queued job. Cancel it first."
        )
    
    await db.delete(job)
    await db.commit()


@router.get("/{job_uuid}/logs", response_model=List[JobLogResponse])
async def get_job_logs(
    job_uuid: str,
    limit: int = Query(100, ge=1, le=1000),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get job execution logs.
    
    Args:
        job_uuid: Job UUID
        limit: Maximum number of log entries
        user_id: Current user ID
        db: Database session
        
    Returns:
        List of log entries
        
    Raises:
        HTTPException: If job not found
    """
    # Get job - shared dashboard: any user can view logs
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Get logs
    result = await db.execute(
        select(JobLog)
        .where(JobLog.job_id == job.id)
        .order_by(desc(JobLog.timestamp))
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return logs


@router.get("/{job_uuid}/download")
async def download_job_result(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download job result file.
    
    Args:
        job_uuid: Job UUID
        user_id: Current user ID
        db: Database session
        
    Returns:
        File download response
        
    Raises:
        HTTPException: If job not found or no output file
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    # Get job - shared dashboard: any user can download results
    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if not job.output_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No output file available for this job"
        )
    
    file_path = Path(job.output_file_path)
    
    # Handle Docker path to Windows path conversion
    if not file_path.exists():
        # Convert Docker path /app/ to actual Windows path
        file_path_str = str(job.output_file_path).replace('/app/', str(settings.BASE_DIR) + '\\')
        file_path_str = file_path_str.replace('/', '\\')
        file_path = Path(file_path_str)
        logger.info(f"Converted Docker path to Windows path for download: {file_path}")
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Output file not found on disk: {file_path}"
        )
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream"
    )


def _get_celery_priority(job_priority):
    """Convert job priority to Celery priority (0-9)."""
    priority_map = {
        "low": 3,
        "normal": 5,
        "high": 7,
        "urgent": 9
    }
    return priority_map.get(job_priority.value, 5)
