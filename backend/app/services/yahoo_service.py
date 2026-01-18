from __future__ import annotations

from backend.app.db import models
from core.sources.yahoo import search_isin
from core.utils.hashing import sha256_text


def ingest_yahoo_isin(isin: str) -> str | None:
    result = search_isin(isin)
    if not result:
        return None
    normalized = result.product.model_dump()
    return models.upsert_product(
        normalized=normalized,
        raw_text=result.raw_json,
        source_kind=result.source_kind,
        source_file_path=None,
        source_file_hash_sha256=sha256_text(f"yahoo:{isin}"),
    )
