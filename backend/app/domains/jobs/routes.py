"""Job routes: create, list, start/pause/resume/cancel/retry, logs, download.

The dashboard is shared: every authenticated user sees and controls every job.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.db import get_db
from app.domains.jobs.models import Job, JobLog, JobStatus
from app.domains.jobs.schemas import (
    JobCreate,
    JobListResponse,
    JobLogResponse,
    JobResponse,
    JobUpdate,
)
from app.domains.jobs.services import (
    cancel_orphaned_jobs,
    get_job_or_404,
    queue_job,
    revoke_task,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    """Create the job record. Upload a file and call /start to run it."""
    job = Job(
        user_id=int(user_id),
        job_uuid=str(uuid.uuid4()),
        tool_type=job_data.tool_type,
        name=job_data.name,
        description=job_data.description,
        priority=job_data.priority,
        config=job_data.config or {},
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status_filter: JobStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(Job)
    if status_filter:
        query = query.where(Job.status == status_filter)
    query = query.order_by(desc(Job.created_at))

    total = (await db.execute(select(func.count()).select_from(query.alias()))).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    return {"jobs": result.scalars().all(), "total": total, "page": page, "page_size": page_size}


@router.get("/{job_uuid}", response_model=JobResponse)
async def get_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    return await get_job_or_404(db, job_uuid)


@router.patch("/{job_uuid}", response_model=JobResponse)
async def update_job(
    job_uuid: str,
    job_update: JobUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    """Update name/description/priority/config of a pending or failed job."""
    job = await get_job_or_404(db, job_uuid)
    if job.status not in [JobStatus.PENDING, JobStatus.FAILED]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Can only update pending or failed jobs")

    for field, value in job_update.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_uuid}/start", response_model=JobResponse)
async def start_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    """Queue the job on the scraper worker."""
    job = await get_job_or_404(db, job_uuid)

    if job.status not in [JobStatus.PENDING, JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot start job with status: {job.status}"
        )
    if not job.input_file_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No input file uploaded for this job")

    logger.info(
        "[START JOB] %s input=%s output=%s", job_uuid, job.input_file_path, job.output_file_path
    )
    await cancel_orphaned_jobs(db, keep_uuid=job_uuid)

    job.celery_task_id = queue_job(job)
    job.status = JobStatus.QUEUED
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_uuid}/cancel", response_model=JobResponse)
async def cancel_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    job = await get_job_or_404(db, job_uuid)
    if job.status not in [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot cancel job with status: {job.status}"
        )

    logger.info("[CANCEL] job=%s task=%s status=%s", job_uuid, job.celery_task_id, job.status)

    # Mark cancelled first so the task loop stops on its next status check,
    # then terminate the worker process (SIGTERM, SIGKILL fallback).
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(job)

    if job.celery_task_id:
        try:
            revoke_task(job.celery_task_id, "SIGTERM")
            await asyncio.sleep(2)
            revoke_task(job.celery_task_id, "SIGKILL")
        except Exception as exc:  # noqa: BLE001
            logger.error("[CANCEL] Failed to terminate task: %s", exc, exc_info=True)
    else:
        logger.warning("[CANCEL] No celery_task_id found for job %s", job_uuid)

    return job


@router.post("/{job_uuid}/pause", response_model=JobResponse)
async def pause_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    job = await get_job_or_404(db, job_uuid)
    if job.status not in [JobStatus.RUNNING, JobStatus.RETRYING]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot pause job with status: {job.status}"
        )

    job.status = JobStatus.PAUSED
    await db.commit()
    await db.refresh(job)
    logger.info("[PAUSE] Job %s paused", job_uuid)
    return job


@router.post("/{job_uuid}/resume", response_model=JobResponse)
async def resume_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    job = await get_job_or_404(db, job_uuid)
    if job.status != JobStatus.PAUSED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot resume job with status: {job.status}"
        )

    job.status = JobStatus.RUNNING
    await db.commit()
    await db.refresh(job)
    logger.info("[RESUME] Job %s resumed", job_uuid)
    return job


@router.post("/{job_uuid}/retry", response_model=JobResponse)
async def retry_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Job:
    """Re-queue a failed or cancelled job; the worker resumes from the output file."""
    job = await get_job_or_404(db, job_uuid)
    if job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot retry job with status: {job.status}. "
            "Only FAILED or CANCELLED jobs can be retried.",
        )

    job.status = JobStatus.RETRYING
    job.completed_at = None
    await db.commit()
    await db.refresh(job)

    job.celery_task_id = queue_job(job)
    job.status = JobStatus.QUEUED
    await db.commit()
    await db.refresh(job)
    logger.info("[RETRY] Job %s requeued with task ID: %s", job_uuid, job.celery_task_id)
    return job


@router.delete("/{job_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job_or_404(db, job_uuid)
    if job.status in [JobStatus.RUNNING, JobStatus.QUEUED]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot delete running or queued job. Cancel it first."
        )
    await db.delete(job)
    await db.commit()


@router.get("/{job_uuid}/logs", response_model=list[JobLogResponse])
async def get_job_logs(
    job_uuid: str,
    limit: int = Query(100, ge=1, le=1000),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    job = await get_job_or_404(db, job_uuid)
    result = await db.execute(
        select(JobLog).where(JobLog.job_id == job.id).order_by(desc(JobLog.timestamp)).limit(limit)
    )
    return result.scalars().all()


@router.get("/{job_uuid}/download")
async def download_job_result(
    job_uuid: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    job = await get_job_or_404(db, job_uuid)
    if not job.output_file_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No output file available for this job")

    file_path = Path(job.output_file_path)
    if not file_path.exists():
        # Paths written inside Docker start with /app/ - remap to this checkout.
        remapped = str(job.output_file_path).replace("/app/", str(get_settings().BASE_DIR) + "/")
        file_path = Path(remapped)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Output file not found on disk: {file_path}"
        )

    return FileResponse(
        path=file_path, filename=file_path.name, media_type="application/octet-stream"
    )
