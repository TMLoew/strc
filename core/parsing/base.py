from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.models import NormalizedProduct


@dataclass
class ParseContext:
    source: str
    raw_text: str
    file_path: Path | None = None


class Parser:
    def parse(self, path: Path, raw_text: str) -> NormalizedProduct:
        raise NotImplementedError


def detect_issuer(raw_text: str) -> str:
    lowered = raw_text.lower()
    if "structuredproducts-ch.leonteq.com" in lowered or "leonteq" in lowered:
        return "leonteq"
    if "luzerner kantonalbank" in lowered:
        return "lukb_style"
    if "swissquote" in lowered:
        return "swissquote"
    if "banque cantonale vaudoise" in lowered or "bcv" in lowered:
        return "bcv"
    return "generic"
