"""Job DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.shared.schemas import JobPriority, JobStatus, ToolType


class JobConfigBase(BaseModel):
    """Base configuration for all tools."""

    max_workers: int = Field(default=3, ge=1, le=5)
    headless_mode: bool = True
    timeout: int = Field(default=30, ge=10, le=120)


class CompanyInfoConfig(JobConfigBase):
    """Configuration specific to the company.info scraper."""

    email: str
    password: str
    implicit_wait: int = Field(default=5, ge=2, le=30)
    page_load_timeout: int = Field(default=30, ge=10, le=120)
    preferred_phone_prefix: str = "06"
    fallback_phone_prefix: str = "05"


class JobCreate(BaseModel):
    tool_type: ToolType
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    priority: JobPriority = JobPriority.NORMAL
    config: dict[str, Any] | None = None


class JobUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: JobPriority | None = None
    config: dict[str, Any] | None = None


class JobResponse(BaseModel):
    id: int
    job_uuid: str
    user_id: int
    tool_type: ToolType
    name: str
    description: str | None
    status: JobStatus
    priority: JobPriority
    progress: float

    input_file_path: str | None
    output_file_path: str | None
    display_filename: str | None

    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int

    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    estimated_completion: datetime | None

    error_message: str | None
    retry_count: int

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobProgressUpdate(BaseModel):
    progress: float = Field(..., ge=0, le=100)
    processed_rows: int
    successful_rows: int
    failed_rows: int
    message: str | None = None


class JobLogCreate(BaseModel):
    level: str = "INFO"
    message: str
    metadata: dict[str, Any] | None = None


class JobLogResponse(BaseModel):
    id: int
    job_id: int
    timestamp: datetime
    level: str
    message: str
    metadata: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class ToolConfigCreate(BaseModel):
    tool_type: ToolType
    name: str
    description: str | None = None
    config: dict[str, Any]
    is_default: bool = False


class ToolConfigResponse(BaseModel):
    id: int
    tool_type: ToolType
    name: str
    description: str | None
    config: dict[str, Any]
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
