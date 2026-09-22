"""File DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    filename: str
    file_path: str
    size: int
    uploaded_at: datetime


class FileListResponse(BaseModel):
    files: list[dict[str, Any]]
    total: int


class HeaderInfo(BaseModel):
    """Header row of an uploaded file, for the column-mapping step."""

    headers: list[str]
    sheet: str | None = None
    header_row: int = 1
    file_type: str | None = None
    detected: dict[str, str] = {}
