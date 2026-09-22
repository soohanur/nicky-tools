"""System routes: health, stats, worker status and worker configuration."""

from __future__ import annotations

import subprocess
from datetime import datetime

import psutil
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.db import get_db
from app.core.task_queue import celery_app
from app.domains.jobs.models import Job, JobStatus
from app.domains.system.schemas import (
    HealthCheck,
    SystemStats,
    WorkerConfig,
    WorkerConfigUpdate,
    WorkerConfigUpdateResponse,
)

router = APIRouter(prefix="/system", tags=["System"])

CELERY_SERVICE = "datainfo-celery"  # systemd unit on the VPS


def _write_env_value(key: str, value: str) -> None:
    """Persist ``key=value`` into the repo-root .env (create the line if missing)."""
    env_file = get_settings().BASE_DIR / ".env"
    if not env_file.exists():
        return
    lines = env_file.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            break
    else:
        lines.append(f"{key}={value}\n")
    env_file.write_text("".join(lines))


def _restart_celery() -> bool:
    """Restart the worker service when running under systemd. False otherwise."""
    try:
        probe = subprocess.run(
            ["systemctl", "is-active", CELERY_SERVICE], capture_output=True, text=True, timeout=5
        )
        if probe.returncode == 0 or "active" in probe.stdout:
            subprocess.run(["sudo", "systemctl", "restart", CELERY_SERVICE], check=True, timeout=10)
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        pass
    return False


@router.post("/config/workers", response_model=WorkerConfigUpdateResponse)
async def update_worker_config(
    config: WorkerConfigUpdate,
    user_id: str = Depends(get_current_user),
) -> dict:
    """Set the parallel worker count; persists to .env and restarts the worker."""
    settings = get_settings()
    try:
        settings.MAX_WORKERS = config.max_workers
        _write_env_value("MAX_WORKERS", str(config.max_workers))
        if _restart_celery():
            message = (
                f"Worker configuration updated to {config.max_workers} workers. "
                "Celery service restarted."
            )
        else:
            message = (
                f"Worker configuration updated to {config.max_workers} workers. "
                "Restart Celery manually to apply changes."
            )
        return {"success": True, "max_workers": config.max_workers, "message": message}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to update configuration: {exc}"
        ) from exc


@router.get("/config/workers", response_model=WorkerConfig)
async def get_worker_config(user_id: str = Depends(get_current_user)) -> dict:
    s = get_settings()
    return {"max_workers": s.MAX_WORKERS, "max_concurrent_jobs": s.MAX_CONCURRENT_JOBS}


@router.get("/health", response_model=HealthCheck)
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Status of API, database, Redis and Celery workers."""
    s = get_settings()

    try:
        await db.execute(select(1))
        db_status = "healthy"
    except Exception as exc:  # noqa: BLE001
        db_status = f"unhealthy: {exc}"

    try:
        from redis import Redis

        Redis.from_url(s.REDIS_URL).ping()
        redis_status = "healthy"
    except Exception as exc:  # noqa: BLE001
        redis_status = f"unhealthy: {exc}"

    try:
        stats = celery_app.control.inspect().stats()
        celery_status = f"healthy ({len(stats)} workers)" if stats else "no workers"
    except Exception as exc:  # noqa: BLE001
        celery_status = f"unhealthy: {exc}"

    healthy = db_status == "healthy" and redis_status == "healthy" and "healthy" in celery_status
    return {
        "status": "healthy" if healthy else "degraded",
        "version": s.APP_VERSION,
        "timestamp": datetime.utcnow(),
        "database": db_status,
        "redis": redis_status,
        "celery": celery_status,
    }


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(db: AsyncSession = Depends(get_db)) -> dict:
    """Resource usage plus today's job counters."""
    s = get_settings()
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(s.BASE_DIR))
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    async def count(*where) -> int:
        result = await db.execute(select(func.count()).select_from(Job).where(*where))
        return result.scalar() or 0

    active_jobs = await count(Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED]))
    queued_jobs = await count(Job.status == JobStatus.QUEUED)
    completed_today = await count(Job.status == JobStatus.COMPLETED, Job.completed_at >= today)
    failed_today = await count(Job.status == JobStatus.FAILED, Job.completed_at >= today)

    total_today = completed_today + failed_today
    success_rate = (completed_today / total_today * 100) if total_today else 100.0

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "disk_percent": disk.percent,
        "active_jobs": active_jobs,
        "queued_jobs": queued_jobs,
        "completed_jobs_today": completed_today,
        "failed_jobs_today": failed_today,
        "success_rate": round(success_rate, 2),
    }


@router.get("/workers")
async def get_worker_status() -> dict:
    """Celery worker inventory."""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        registered = inspect.registered() or {}
        workers = [
            {
                "name": name,
                "status": "online",
                "pool": w.get("pool", {}).get("implementation", "unknown"),
                "max_concurrency": w.get("pool", {}).get("max-concurrency", 0),
                "active_tasks": len(active.get(name, [])),
                "registered_tasks": len(registered.get(name, [])),
            }
            for name, w in stats.items()
        ]
        return {"workers": workers, "total_workers": len(workers)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "workers": [], "total_workers": 0}


@router.get("/debug/jobs")
async def debug_jobs(db: AsyncSession = Depends(get_db)) -> dict:
    """Last 10 jobs, unauthenticated (ops debugging)."""
    result = await db.execute(select(Job).order_by(desc(Job.created_at)).limit(10))
    return {
        "jobs": [
            {
                "uuid": j.job_uuid[:8],
                "status": j.status.value,
                "filename": j.display_filename,
                "total": j.total_rows,
                "processed": j.processed_rows,
                "created": j.created_at.isoformat() if j.created_at else None,
                "completed": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in result.scalars().all()
        ]
    }
