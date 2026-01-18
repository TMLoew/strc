from __future__ import annotations

import json
from pathlib import Path

import httpx

from backend.app.db import models
from backend.app.settings import settings
from backend.app.services.leonteq_session_service import get_leonteq_session_state
from core.models import NormalizedProduct
from core.sources.leonteq import fetch_authenticated_html, fetch_public_html, parse_public_html
from core.sources.pdf_termsheet import extract_text, parse_pdf
from core.utils.hashing import sha256_text
from core.utils.merge import merge_products
from core.utils.cache import read_cached_source, write_cached_source

PREFER_PDF_FIELDS = {
    "coupon_rate_pct_pa",
    "coupon_frequency",
    "coupon_is_guaranteed",
    "coupon_schedule",
    "barrier_type",
    "barrier_observation_start",
    "barrier_observation_end",
    "barrier_trigger_condition",
    "worst_of",
    "worst_of_definition",
    "settlement_type",
    "redemption_rules",
    "physical_delivery",
    "payoff_summary_text",
}


def _download_pdf(url: str, target: Path) -> None:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        target.write_bytes(response.content)


def ingest_leonteq_isin(isin: str) -> str:
    cached = read_cached_source("leonteq", isin)
    html = cached or fetch_public_html(isin)
    if cached is None:
        write_cached_source("leonteq", isin, html)
    result = parse_public_html(html, isin)
    product = result.product

    source_kind = result.source_kind
    session_state = get_leonteq_session_state()
    if session_state:
        try:
            auth_html = fetch_authenticated_html(isin, session_state)
            auth_result = parse_public_html(auth_html, isin)
            product = merge_products(auth_result.product, product)
            source_kind = "leonteq_html_auth"
        except Exception:
            pass
    if result.pdf_url:
        settings.data_dir.joinpath("cache").mkdir(parents=True, exist_ok=True)
        pdf_path = settings.data_dir / "cache" / f"{isin}.pdf"
        _download_pdf(result.pdf_url, pdf_path)
        raw_text = extract_text(pdf_path)
        pdf_product = parse_pdf(pdf_path, raw_text)
        product = merge_products(product, pdf_product, prefer_secondary_fields=PREFER_PDF_FIELDS)
        source_kind = "mixed"
    else:
        raw_text = None

    normalized = product.model_dump()
    return models.upsert_product(
        normalized=normalized,
        raw_text=raw_text,
        source_kind=source_kind,
        source_file_path=None,
        source_file_hash_sha256=sha256_text(f"leonteq:{isin}"),
    )
