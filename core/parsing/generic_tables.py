from __future__ import annotations

from pathlib import Path

from core.models import NormalizedProduct


class GenericTableParser:
    def parse(self, path: Path, raw_text: str) -> NormalizedProduct:
        return NormalizedProduct()
