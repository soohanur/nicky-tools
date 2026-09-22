"""Canonical enums and cross-domain DTOs.

The enums mirror the SQLAlchemy ones in ``app.domains.jobs.models`` so API
schemas never import ORM classes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ToolType(str, Enum):
    SCRAPLY = "scraply"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebSocketMessage(BaseModel):
    type: str  # "job_update", "log", "system_alert"
    job_uuid: str | None = None
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
