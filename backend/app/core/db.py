"""Declarative Base + async engine/session factory.

Models must NOT import services or routes. This module has no business logic.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import get_settings

_settings = get_settings()

# SQLite (tests / local smoke runs) does not accept pool sizing arguments.
_pool_kwargs = {} if _settings.is_sqlite else {"pool_size": 20, "max_overflow": 40}

engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    **_pool_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency - one session per request, committed on success."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables that are missing (Alembic owns real migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
