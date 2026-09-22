"""Background worker entrypoint (Celery).

Run:  celery -A app.worker worker --loglevel=info --concurrency=1 --pool=prefork

Importing this module registers the scraper tasks (``app.domains.scraply.tasks``)
on the shared Celery app defined in ``app.core.task_queue``.
"""

from __future__ import annotations

from app.core.logging import configure_logging
from app.core.task_queue import celery_app

configure_logging()

# Registers run_automation_job / run_scraply_tool on celery_app.
import app.domains.scraply.tasks  # noqa: E402, F401

__all__ = ["celery_app"]
