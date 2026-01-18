from __future__ import annotations

from backend.app.db import models
from core.sources.finanzen import fetch_html, parse_html
from core.utils.hashing import sha256_text


def ingest_finanzen_isin(isin: str) -> str:
    html = fetch_html(isin)
    result = parse_html(html, isin)
    normalized = result.product.model_dump()
    return models.upsert_product(
        normalized=normalized,
        raw_text=result.raw_html,
        source_kind=result.source_kind,
        source_file_path=None,
        source_file_hash_sha256=sha256_text(f"finanzen:{isin}"),
    )
