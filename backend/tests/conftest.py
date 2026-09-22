"""Test fixtures - in-memory SQLite, no Postgres/Redis/Celery needed."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

# Must be set before app.config is imported (settings are cached on first read).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-admin-key")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

# import every model so Base.metadata.create_all is complete
import app.auth.models  # noqa: E402, F401
import app.domains.jobs.models  # noqa: E402, F401
import app.domains.system.models  # noqa: E402, F401
from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with sm() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Register + login a user; returns the bearer header."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "tester@example.com",
            "username": "tester",
            "password": "password123",
            "admin_key": "test-admin-key",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "tester", "password": "password123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
