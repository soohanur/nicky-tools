"""Logging setup shared by the API and the Celery worker."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=_FORMAT)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
