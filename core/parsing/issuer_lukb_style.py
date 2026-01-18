from __future__ import annotations

from pathlib import Path

from core.models import NormalizedProduct
from core.parsing.generic_regex import GenericRegexParser


class LUKBStyleParser:
    def parse(self, path: Path, raw_text: str) -> NormalizedProduct:
        return GenericRegexParser().parse(path, raw_text)
