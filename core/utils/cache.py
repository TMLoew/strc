from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parents[2]


def cache_dir() -> Path:
    data_dir = Path(os.getenv("SPA_DATA_DIR", BASE_DIR / "data"))
    target = data_dir / "cache" / "sources"
    target.mkdir(parents=True, exist_ok=True)
    return target


def read_cached_source(source: str, key: str) -> Optional[str]:
    path = cache_dir() / source / f"{key}.html"
    if not path.exists():
        return None
    return path.read_text()


def write_cached_source(source: str, key: str, content: str) -> Path:
    base = cache_dir() / source
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{key}.html"
    if path.exists():
        existing = path.read_text()
        if existing != content:
            archive_dir = base / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            archive_path = archive_dir / f"{key}-{timestamp}.html"
            archive_path.write_text(existing)
    path.write_text(content)
    return path
