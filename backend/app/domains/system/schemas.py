"""System DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database: str
    redis: str
    celery: str


class SystemStats(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_jobs: int
    queued_jobs: int
    completed_jobs_today: int
    failed_jobs_today: int
    success_rate: float


class WorkerConfig(BaseModel):
    max_workers: int
    max_concurrent_jobs: int


class WorkerConfigUpdate(BaseModel):
    max_workers: int = Field(ge=1, le=12, description="Parallel browser workers (1-12)")


class WorkerConfigUpdateResponse(BaseModel):
    success: bool
    max_workers: int
    message: str
