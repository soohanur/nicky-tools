"""Liveness / readiness (unauthenticated).

``/health`` is kept because the existing nginx and deploy checks call it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db import get_db
from app.shared.schemas import HealthResponse

router = APIRouter(tags=["health"])


def _payload(status: str = "ok") -> HealthResponse:
    s = get_settings()
    return HealthResponse(status=status, version=s.APP_VERSION, environment=s.ENVIRONMENT)


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return _payload()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return _payload("healthy")


@router.get("/readyz", response_model=HealthResponse)
async def readyz(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    await db.execute(text("SELECT 1"))
    return _payload("ready")
