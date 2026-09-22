"""File routes: upload, list, download, delete, header detection."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.db import get_db
from app.domains.files.schemas import FileListResponse, FileUploadResponse, HeaderInfo
from app.domains.files.services import (
    ALLOWED_EXTENSIONS,
    file_entry,
    next_display_name,
    read_headers,
    split_name,
    storage_paths,
)
from app.domains.jobs.models import Job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    job_uuid: str = Query(..., description="Job UUID to associate with upload"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store the input file for a job (.csv, .xlsx, .xls)."""
    settings = get_settings()

    if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large. Max size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB",
        )

    result = await db.execute(
        select(Job).where(Job.job_uuid == job_uuid, Job.user_id == int(user_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    base_name, _ = split_name(file.filename)
    result = await db.execute(
        select(Job)
        .where(Job.user_id == int(user_id), Job.display_filename.like(f"{base_name}%"))
        .order_by(Job.created_at.desc())
    )
    display_filename = next_display_name(file.filename, result.scalars().all())

    input_path, output_path = storage_paths(job_uuid, file.filename, display_filename)
    input_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(input_path, "wb") as f:
        await f.write(content)

    job.input_file_path = str(input_path)
    job.output_file_path = str(output_path)
    job.display_filename = display_filename
    await db.commit()

    return {
        "filename": input_path.name,
        "file_path": str(input_path),
        "size": len(content),
        "uploaded_at": datetime.utcnow(),
    }


@router.get("/inputs", response_model=FileListResponse)
async def list_input_files(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Input files of the current user's jobs, newest first."""
    result = await db.execute(
        select(Job)
        .where(Job.user_id == int(user_id), Job.input_file_path.isnot(None))
        .order_by(Job.created_at.desc())
    )
    files = []
    for job in result.scalars().all():
        entry = file_entry(
            Path(job.input_file_path), job.display_filename or Path(job.input_file_path).name
        )
        if entry:
            files.append(entry)
    return {"files": files, "total": len(files)}


@router.get("/outputs", response_model=FileListResponse)
async def list_output_files(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Job)
        .where(Job.user_id == int(user_id), Job.output_file_path.isnot(None))
        .order_by(Job.created_at.desc())
    )
    files = []
    for job in result.scalars().all():
        entry = file_entry(Path(job.output_file_path))
        if entry:
            files.append(entry)
    return {"files": files, "total": len(files)}


@router.get("/download/{filename}")
async def download_file(filename: str, user_id: str = Depends(get_current_user)) -> FileResponse:
    s = get_settings()
    file_path = s.scraply_output_dir / filename
    if not file_path.exists():
        file_path = s.scraply_input_dir / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    filename: str,
    file_type: str = Query(..., regex="^(input|output)$"),
    user_id: str = Depends(get_current_user),
):
    s = get_settings()
    base = s.scraply_input_dir if file_type == "input" else s.scraply_output_dir
    file_path = base / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    file_path.unlink()


@router.get("/csv-headers/{filename}", response_model=HeaderInfo)
async def get_csv_headers(filename: str, user_id: str = Depends(get_current_user)) -> dict:
    """Column headers of an uploaded file, for the mapping step."""
    file_path = get_settings().scraply_input_dir / filename
    if not file_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    if file_path.suffix.lower() not in (".csv", ".xlsx", ".xlsm", ".xls"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Unsupported file type. Only CSV and Excel files are supported.",
        )
    try:
        return read_headers(file_path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error reading file headers: {exc}"
        ) from exc
