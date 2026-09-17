"""
File upload and management routes
"""
import logging
import os
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..db.models import Job
from ..schemas.schemas import FileUploadResponse, FileListResponse
from ..core.security import get_current_user
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    job_uuid: str = Query(..., description="Job UUID to associate with upload"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload input file for a job.
    
    Accepts CSV or Excel files (.csv, .xlsx, .xls).
    
    Args:
        file: File to upload
        job_uuid: Job to associate file with
        user_id: Current user ID
        db: Database session
        
    Returns:
        Upload confirmation with file details
        
    Raises:
        HTTPException: If file type invalid or job not found
    """
    # Validate file type
    allowed_extensions = {'.csv', '.xlsx', '.xls'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Check file size
    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )
    
    await file.seek(0)  # Reset file pointer
    
    # Get job
    result = await db.execute(
        select(Job).where(
            Job.job_uuid == job_uuid,
            Job.user_id == int(user_id)
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Generate display filename with duplicate handling
    base_name = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
    extension = file.filename.rsplit('.', 1)[1] if '.' in file.filename else ''
    display_filename = file.filename
    
    # Check for duplicate display names for this user
    result = await db.execute(
        select(Job).where(
            Job.user_id == int(user_id),
            Job.display_filename.like(f"{base_name}%")
        ).order_by(Job.created_at.desc())
    )
    existing_jobs = result.scalars().all()
    
    if existing_jobs:
        # Find highest number suffix
        max_num = 0
        for existing_job in existing_jobs:
            if not existing_job.display_filename:
                continue
            existing_name = existing_job.display_filename
            # Check for exact match or (N) suffix
            if existing_name == file.filename:
                max_num = max(max_num, 1)
            elif existing_name.startswith(base_name):
                # Extract number from (N) pattern
                import re
                match = re.search(r'\((\d+)\)\.' + re.escape(extension) + '$', existing_name)
                if match:
                    max_num = max(max_num, int(match.group(1)))
        
        # Add suffix if duplicates found
        if max_num > 0:
            display_filename = f"{base_name} ({max_num + 1}).{extension}" if extension else f"{base_name} ({max_num + 1})"
    
    # Generate unique filename for storage
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{job_uuid}_{timestamp}_{file.filename}"
    
    # Use the environment-aware directory paths
    input_dir = settings.scraply_input_dir
    output_dir = settings.scraply_output_dir
    
    file_path = input_dir / safe_filename
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Update job with file path and display name
    output_filename = f"DONE_{display_filename}"
    output_path = output_dir / f"{job_uuid}_{timestamp}_{output_filename}"
    
    # Store paths as strings (they will be Docker paths when running in Docker)
    job.input_file_path = str(file_path)
    job.output_file_path = str(output_path)
    job.display_filename = display_filename
    
    await db.commit()
    
    return {
        "filename": safe_filename,
        "file_path": str(file_path),
        "size": file_size,
        "uploaded_at": datetime.utcnow()
    }


@router.get("/inputs", response_model=FileListResponse)
async def list_input_files(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all uploaded input files for current user.
    
    Args:
        user_id: Current user ID
        db: Database session
        
    Returns:
        List of input files with original display names
    """
    files = []
    
    # Query user's jobs to get their uploaded files
    result = await db.execute(
        select(Job).where(
            Job.user_id == int(user_id),
            Job.input_file_path.isnot(None)
        ).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    
    # Build file list from user's jobs only
    for job in jobs:
        if job.input_file_path:
            file_path = Path(job.input_file_path)
            
            # Check if file exists
            if file_path.exists() and file_path.is_file():
                stat = file_path.stat()
                stored_filename = file_path.name
                display_name = job.display_filename or stored_filename
                
                files.append({
                    "filename": stored_filename,  # Keep stored name for download/delete
                    "display_name": display_name,  # Show original name to user
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    
    return {
        "files": files,  # Already sorted by job.created_at desc
        "total": len(files)
    }


@router.get("/outputs", response_model=FileListResponse)
async def list_output_files(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all output files for current user.
    
    Args:
        user_id: Current user ID
        db: Database session
        
    Returns:
        List of output files
    """
    files = []
    
    # Query user's jobs to get their output files
    result = await db.execute(
        select(Job).where(
            Job.user_id == int(user_id),
            Job.output_file_path.isnot(None)
        ).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    
    # Build file list from user's jobs only
    for job in jobs:
        if job.output_file_path:
            file_path = Path(job.output_file_path)
            
            # Check if file exists
            if file_path.exists() and file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    
    return {
        "files": files,  # Already sorted by job.created_at desc
        "total": len(files)
    }


@router.get("/download/{filename}")
async def download_file(
    filename: str,
    user_id: str = Depends(get_current_user)
):
    """
    Download output file.
    
    Args:
        filename: Name of file to download
        user_id: Current user ID
        
    Returns:
        File download response
        
    Raises:
        HTTPException: If file not found
    """
    # Check in output directory
    file_path = settings.scraply_output_dir / filename
    
    if not file_path.exists():
        # Try input directory as fallback
        file_path = settings.scraply_input_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    filename: str,
    file_type: str = Query(..., regex="^(input|output)$"),
    user_id: str = Depends(get_current_user)
):
    """
    Delete a file.
    
    Args:
        filename: Name of file to delete
        file_type: Type of file ('input' or 'output')
        user_id: Current user ID
        
    Raises:
        HTTPException: If file not found
    """
    if file_type == "input":
        file_path = settings.scraply_input_dir / filename
    else:
        file_path = settings.scraply_output_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    file_path.unlink()


@router.get("/csv-headers/{filename}")
async def get_csv_headers(
    filename: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get CSV column headers from an uploaded file.
    
    Args:
        filename: Name of the uploaded CSV file
        user_id: Current user ID
        
    Returns:
        List of column headers
        
    Raises:
        HTTPException: If file not found or not a valid CSV
    """
    import csv
    import pandas as pd
    
    file_path = settings.scraply_input_dir / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    file_ext = file_path.suffix.lower()
    if file_ext not in ('.csv', '.xlsx', '.xlsm', '.xls'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only CSV and Excel files are supported."
        )

    try:
        # Detect the real header row (some exports carry a group-label row above
        # it) so the dropdown lists the actual column names. The column mapping
        # itself is NOT suggested: exports vary too much between deliveries and a
        # wrong pre-fill is easy to miss, so the user picks every field by hand.
        try:
            from src.modules.kadaster_map import detect_any
            det = detect_any(file_path)
            headers = [h for h in det.get("headers", []) if h]
            if headers:
                return {
                    "headers": headers,
                    "sheet": det.get("sheet"),
                    "header_row": det.get("header_row", 1),
                    "file_type": det.get("file_type"),
                    "detected": {},
                }
        except Exception as detect_err:
            logger.warning(f"Header detection failed for {filename}: {detect_err}")

        # Fallback: plain first-row read.
        if file_ext == '.csv':
            for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        names = csv.DictReader(f).fieldnames
                        if names:
                            return {"headers": [h.strip() for h in names if h and h.strip()],
                                    "sheet": None, "header_row": 1,
                                    "file_type": "csv", "detected": {}}
                except UnicodeDecodeError:
                    continue
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Could not decode CSV file")

        df = pd.read_excel(file_path, nrows=0)
        return {"headers": df.columns.tolist(), "sheet": None, "header_row": 1,
                "file_type": "excel", "detected": {}}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file headers: {str(e)}"
        )
