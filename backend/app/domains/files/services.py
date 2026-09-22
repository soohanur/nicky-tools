"""File services: display-name dedupe, storage paths, header detection."""

from __future__ import annotations

import csv
import logging
import re
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.domains.jobs.models import Job

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# The scraper engine (<repo>/scraply) is a sibling package, not a dependency;
# make its ``src`` importable for header detection.
_scraply_dir = get_settings().BASE_DIR / "scraply"
if str(_scraply_dir) not in sys.path:
    sys.path.insert(0, str(_scraply_dir))


def split_name(filename: str) -> tuple[str, str]:
    """('report', 'xlsx') for 'report.xlsx'; ('report', '') without extension."""
    if "." in filename:
        base, ext = filename.rsplit(".", 1)
        return base, ext
    return filename, ""


def next_display_name(filename: str, existing_jobs: Iterable[Job]) -> str:
    """Return ``filename`` or ``filename (N)`` so a user's uploads stay distinct."""
    base_name, extension = split_name(filename)
    max_num = 0
    for job in existing_jobs:
        name = job.display_filename
        if not name:
            continue
        if name == filename:
            max_num = max(max_num, 1)
        elif name.startswith(base_name):
            match = re.search(r"\((\d+)\)\." + re.escape(extension) + "$", name)
            if match:
                max_num = max(max_num, int(match.group(1)))
    if max_num == 0:
        return filename
    suffix = f"{base_name} ({max_num + 1})"
    return f"{suffix}.{extension}" if extension else suffix


def storage_paths(job_uuid: str, original_name: str, display_name: str) -> tuple[Path, Path]:
    """(input_path, output_path) for a new upload, timestamped to stay unique."""
    s = get_settings()
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    input_path = s.scraply_input_dir / f"{job_uuid}_{stamp}_{original_name}"
    output_path = s.scraply_output_dir / f"{job_uuid}_{stamp}_DONE_{display_name}"
    return input_path, output_path


def file_entry(path: Path, display_name: str | None = None) -> dict | None:
    """Directory-listing entry for ``path`` or None when it is gone."""
    if not path.exists() or not path.is_file():
        return None
    stat = path.stat()
    entry = {
        "filename": path.name,
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }
    if display_name is not None:
        entry["display_name"] = display_name
    return entry


def read_headers(file_path: Path) -> dict:
    """Header row of a CSV/Excel upload.

    Uses the scraper's ``kadaster_map.detect_any`` first: some exports carry a
    group-label row above the real headers and it finds the right one. The
    mapping itself is never suggested; the user picks every field by hand.
    """
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
    except Exception as exc:  # noqa: BLE001
        logger.warning("Header detection failed for %s: %s", file_path.name, exc)

    if file_path.suffix.lower() == ".csv":
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]:
            try:
                with open(file_path, encoding=encoding) as f:
                    names = csv.DictReader(f).fieldnames
                    if names:
                        return {
                            "headers": [h.strip() for h in names if h and h.strip()],
                            "sheet": None,
                            "header_row": 1,
                            "file_type": "csv",
                            "detected": {},
                        }
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not decode CSV file")

    import pandas as pd

    df = pd.read_excel(file_path, nrows=0)
    return {
        "headers": df.columns.tolist(),
        "sheet": None,
        "header_row": 1,
        "file_type": "excel",
        "detected": {},
    }
