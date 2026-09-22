"""Single settings source - cached Pydantic Settings (the only place env is read).

Every value keeps the name it had before the restructure so the existing
``.env`` on the VPS and the scraper task keep working unchanged.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import validator
from pydantic_settings import BaseSettings

from app.core.environment import EnvironmentConfig

# backend/app/config.py -> parents[2] is the repository root
BASE_DIR: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings with environment variable support and smart URL detection."""

    # Application
    APP_NAME: str = "Scraply API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development, staging, production

    # Domain Configuration (for production)
    DOMAIN_NAME: str | None = None  # e.g. "nicky.tools" or the VPS IP
    USE_HTTPS: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 2

    # Security
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_USE_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ADMIN_SECRET_KEY: str = "admin123"  # Change this in production!

    # CORS - can be set explicitly or auto-generated from the environment
    BACKEND_CORS_ORIGINS: str | None = None

    @validator("BACKEND_CORS_ORIGINS", pre=True, always=True)
    def assemble_cors_origins(cls, v, values):
        if v and isinstance(v, str) and v.strip():
            return v
        if isinstance(v, list):
            return ",".join(v)
        return ",".join(EnvironmentConfig.get_cors_origins())

    @property
    def cors_origins(self) -> list[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return EnvironmentConfig.get_cors_origins()
        return [i.strip() for i in self.BACKEND_CORS_ORIGINS.split(",") if i.strip()]

    @property
    def backend_url(self) -> str:
        return EnvironmentConfig.get_backend_url()

    @property
    def frontend_url(self) -> str:
        return EnvironmentConfig.get_frontend_url()

    @property
    def websocket_url(self) -> str:
        return EnvironmentConfig.get_websocket_url()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ["production", "prod"] or not self.DEBUG

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "automation_user"
    POSTGRES_PASSWORD: str = "automation_password"
    POSTGRES_DB: str = "automation_db"
    DATABASE_URL: str | None = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v, values):
        if isinstance(v, str):
            return v
        return (
            f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}"
            f"@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB')}"
        )

    # Redis (job queue and cache)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    REDIS_URL: str | None = None

    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v, values):
        if isinstance(v, str):
            return v
        password_part = f":{values.get('REDIS_PASSWORD')}@" if values.get("REDIS_PASSWORD") else ""
        return (
            f"redis://{password_part}{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}"
            f"/{values.get('REDIS_DB')}"
        )

    # Celery
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    @validator("CELERY_BROKER_URL", pre=True)
    def set_celery_broker(cls, v, values):
        return v or values.get("REDIS_URL")

    @validator("CELERY_RESULT_BACKEND", pre=True)
    def set_celery_backend(cls, v, values):
        return v or values.get("REDIS_URL")

    # File storage - the scraper engine lives in <repo>/scraply
    BASE_DIR: Path = BASE_DIR

    @property
    def scraply_input_dir(self) -> Path:
        if Path("/app/scraply").exists():
            return Path("/app/scraply/csv_files/input")
        return self.BASE_DIR / "scraply" / "csv_files" / "input"

    @property
    def scraply_output_dir(self) -> Path:
        if Path("/app/scraply").exists():
            return Path("/app/scraply/csv_files/output")
        return self.BASE_DIR / "scraply" / "csv_files" / "output"

    UPLOAD_DIR: Path = BASE_DIR / "scraply" / "csv_files" / "input"
    OUTPUT_DIR: Path = BASE_DIR / "scraply" / "csv_files" / "output"
    LOG_DIR: Path = BASE_DIR / "logs"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Job execution
    MAX_CONCURRENT_JOBS: int = 3
    JOB_TIMEOUT: int = 3600 * 36  # 36 hours (large datasets)
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_DELAY: int = 60  # seconds

    # company.info credentials used by the scraper
    COMPANYINFO_EMAIL: str = ""
    COMPANYINFO_PASSWORD: str = ""
    COMPANYINFO_URL: str = "https://company.info"

    # Chrome - shared profiles at the repo root
    CHROME_PROFILES_DIR: Path = BASE_DIR / "chrome_profiles"
    CHROME_PROFILE_PATH: str = str(BASE_DIR / "chrome_profiles" / "default")
    CHROME_PROFILE_NAME: str = "Default"
    HEADLESS_MODE: bool = False
    MAX_WORKERS: int = 3  # per job; total limited by MAX_CONCURRENT_JOBS

    # Monitoring
    SENTRY_DSN: str | None = None
    ENABLE_METRICS: bool = True

    # Email notifications (optional)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    NOTIFICATION_EMAIL: str | None = None

    @property
    def is_sqlite(self) -> bool:
        return (self.DATABASE_URL or "").startswith("sqlite")

    class Config:
        case_sensitive = True
        extra = "ignore"  # ignore scraper-only keys in .env
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    for d in (s.UPLOAD_DIR, s.OUTPUT_DIR, s.LOG_DIR, s.CHROME_PROFILES_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return s


# Module-level instance kept for the scraper task and the worker-config route,
# which read and mutate settings at runtime.
settings = get_settings()
