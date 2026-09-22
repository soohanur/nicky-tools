"""System metrics snapshot (monitoring)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer

from app.core.db import Base


class SystemMetrics(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_percent = Column(Float)

    active_jobs = Column(Integer, default=0)
    queued_jobs = Column(Integer, default=0)
    completed_jobs_today = Column(Integer, default=0)
    failed_jobs_today = Column(Integer, default=0)

    avg_job_duration = Column(Float)  # seconds
    success_rate = Column(Float)  # percentage

    def __repr__(self) -> str:
        return f"<SystemMetrics {self.timestamp}>"
