"""Celery application (Redis broker + result backend).

The scraper task modules are listed in ``include`` so the worker registers them
on boot. Task names are explicit (``run_automation_job`` / ``run_scraply_tool``)
and did not change with the domain layout, so queued messages stay compatible.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "scraply",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.domains.scraply.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.JOB_TIMEOUT,
    task_soft_time_limit=settings.JOB_TIMEOUT - 300,  # 5 minutes before hard limit
    worker_prefetch_multiplier=1,  # one task at a time
    worker_max_tasks_per_child=50,  # restart worker after 50 tasks (memory cleanup)
    task_acks_late=False,  # acknowledge immediately to prevent redelivery
    task_reject_on_worker_lost=True,
    result_expires=3600 * 24 * 7,  # keep results for 7 days
)

# Task routing (for future multi-queue support)
celery_app.conf.task_routes = {
    "app.domains.scraply.tasks.run_scraply_tool": {"queue": "scraply"},
    "app.domains.scraply.tasks.run_automation_job": {"queue": "default"},
}

celery_app.conf.task_default_priority = 5
