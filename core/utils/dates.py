from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_date_de(value: str) -> Optional[str]:
    value = value.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_date_any(value: str) -> Optional[str]:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None
