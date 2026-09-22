"""Job tracking models. Enum class names are unchanged so the Postgres enum
types (``jobstatus``, ``jobpriority``, ``tooltype``) stay valid."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.db import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ToolType(str, enum.Enum):
    SCRAPLY = "scraply"  # company.info scraper


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    job_uuid = Column(String, unique=True, index=True, nullable=False)
    tool_type = Column(SQLEnum(ToolType), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)

    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    priority = Column(SQLEnum(JobPriority), default=JobPriority.NORMAL)
    progress = Column(Float, default=0.0)  # 0-100

    input_file_path = Column(String)
    output_file_path = Column(String)
    display_filename = Column(String)  # user-facing name (may carry a "(N)" suffix)
    config = Column(JSON)  # tool-specific configuration (column mapping etc.)

    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    successful_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_completion = Column(DateTime)

    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    celery_task_id = Column(String, index=True)

    user = relationship("User", back_populates="jobs")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Job {self.job_uuid} - {self.status}>"


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    log_metadata = Column(JSON)

    job = relationship("Job", back_populates="logs")

    def __repr__(self) -> str:
        return f"<JobLog {self.level} - {self.timestamp}>"


class ToolConfig(Base):
    """Saved tool configuration presets."""

    __tablename__ = "tool_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    tool_type = Column(SQLEnum(ToolType), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    config = Column(JSON, nullable=False)
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ToolConfig {self.tool_type} - {self.name}>"
