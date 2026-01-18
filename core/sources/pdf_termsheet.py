from __future__ import annotations

from pathlib import Path

import pdfplumber

from core.models import NormalizedProduct
from core.parsing import GenericRegexParser, LUKBStyleParser, detect_issuer


def extract_text(path: Path) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def parse_pdf(path: Path, raw_text: str) -> NormalizedProduct:
    issuer = detect_issuer(raw_text)
    if issuer == "lukb_style":
        parser = LUKBStyleParser()
    else:
        parser = GenericRegexParser()
    return parser.parse(path, raw_text)
