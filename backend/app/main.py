"""FastAPI app factory + lifespan. Wires routers, CORS and error handlers."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.auth.routes import router as auth_router
from app.config import get_settings
from app.core.db import close_db, init_db
from app.core.logging import configure_logging, get_logger
from app.domains.files.routes import router as files_router
from app.domains.jobs.routes import router as jobs_router
from app.domains.jobs.websocket import router as ws_router
from app.domains.system.routes import router as system_router
from app.health import router as health_router

logger = get_logger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    logger.info(
        "Scraply API starting (env=%s, version=%s)", settings.ENVIRONMENT, settings.APP_VERSION
    )

    await init_db()
    logger.info("database ready")

    try:
        from redis import Redis

        Redis.from_url(settings.REDIS_URL).ping()
        logger.info("redis reachable")
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis unreachable: %s", exc)

    try:
        from app.core.task_queue import celery_app

        stats = celery_app.control.inspect().stats()
        logger.info("celery workers: %s", len(stats) if stats else 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("celery check failed: %s", exc)

    logger.info("docs at %s/docs", settings.backend_url)
    yield

    await close_db()
    logger.info("shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Scraply - company.info contact extraction. Jobs, files, live progress.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # JWT travels in the Authorization header (no cookies), so credentials stay off.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time"] = str(time.time() - start)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Validation error", "errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):  # type: ignore[no-untyped-def]
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error": str(exc) if settings.DEBUG else "An unexpected error occurred",
            },
        )

    app.include_router(health_router)
    app.include_router(auth_router, prefix=settings.API_PREFIX)
    app.include_router(jobs_router, prefix=settings.API_PREFIX)
    app.include_router(files_router, prefix=settings.API_PREFIX)
    app.include_router(system_router, prefix=settings.API_PREFIX)
    app.include_router(ws_router, prefix=settings.API_PREFIX)

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "health": f"{settings.API_PREFIX}/system/health",
        }

    if settings.DEBUG:
        logger.warning("DEBUG MODE ENABLED - do not use in production")

    return app


app = create_app()
