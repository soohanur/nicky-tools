"""Job services: lookups, queueing and Celery task control.

Routes call these; they never touch Celery directly.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from celery.result import AsyncResult
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_queue import celery_app
from app.domains.jobs.models import Job, JobPriority, JobStatus

logger = logging.getLogger(__name__)

_CELERY_PRIORITY = {"low": 3, "normal": 5, "high": 7, "urgent": 9}


def celery_priority(priority: JobPriority) -> int:
    """Map a job priority to Celery's 0-9 scale."""
    return _CELERY_PRIORITY.get(priority.value, 5)


async def get_job_or_404(db: AsyncSession, job_uuid: str) -> Job:
    result = await db.execute(select(Job).where(Job.job_uuid == job_uuid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def revoke_task(task_id: str, signal: str = "SIGTERM") -> None:
    """Revoke + terminate a Celery task (control channel and result backend)."""
    celery_app.control.revoke(task_id, terminate=True, signal=signal)
    AsyncResult(task_id, app=celery_app).revoke(terminate=True, signal=signal)


def config_with_credentials(job: Job) -> dict:
    """Job config plus company.info credentials from the environment when missing."""
    job_config = dict(job.config or {})
    if not job_config.get("email"):
        job_config["email"] = os.environ.get("COMPANYINFO_EMAIL", "")
    if not job_config.get("password"):
        job_config["password"] = os.environ.get("COMPANYINFO_PASSWORD", "")
    return job_config


def queue_job(job: Job) -> str:
    """Send the job to the scraper worker. Returns the Celery task id."""
    from app.domains.scraply.tasks import run_automation_job  # deferred: heavy import

    output_file = job.output_file_path or job.input_file_path.replace("input", "output").replace(
        ".csv", "_DONE.csv"
    )
    task = run_automation_job.apply_async(
        kwargs={
            "job_uuid": job.job_uuid,
            "tool_type": job.tool_type.value,
            "input_file": job.input_file_path,
            "output_file": output_file,
            "config": config_with_credentials(job),
        },
        priority=celery_priority(job.priority),
    )
    return task.id


async def cancel_orphaned_jobs(db: AsyncSession, keep_uuid: str) -> int:
    """Mark stray running/queued jobs cancelled and revoke their tasks.

    Prevents a stuck job from blocking the single scraper queue.
    """
    result = await db.execute(
        select(Job).where(
            Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]),
            Job.job_uuid != keep_uuid,
        )
    )
    orphaned = result.scalars().all()
    for job in orphaned:
        try:
            if job.celery_task_id:
                revoke_task(job.celery_task_id)
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
        except Exception as exc:  # noqa: BLE001
            logger.error("[START JOB] Failed to revoke orphaned task: %s", exc)
    if orphaned:
        await db.commit()
        logger.info("[START JOB] Cleaned up %d orphaned jobs", len(orphaned))
    return len(orphaned)
