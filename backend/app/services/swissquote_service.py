from __future__ import annotations

from backend.app.db import models
from backend.app.settings import settings
from backend.app.services.swissquote_session_service import get_session_state
from core.sources.swissquote import (
    fetch_quote_html,
    fetch_quote_html_playwright,
    fetch_quote_html_playwright_auth,
    fetch_quote_html_playwright_session,
    is_login_page,
    parse_quote_html,
)
from core.utils.hashing import sha256_text
from core.utils.cache import read_cached_source, write_cached_source


def ingest_swissquote_isin(isin: str) -> str | None:
    cached = read_cached_source("swissquote", isin)
    html = cached
    if html is None:
        try:
            session_state = get_session_state()
            if session_state:
                html = fetch_quote_html_playwright_session(isin, session_state)
            elif settings.swissquote_username and settings.swissquote_password:
                html = fetch_quote_html_playwright_auth(
                    isin, settings.swissquote_username, settings.swissquote_password
                )
            else:
                html = fetch_quote_html_playwright(isin)
        except Exception:
            html = fetch_quote_html(isin)
    if is_login_page(html):
        return None
    if cached is None:
        write_cached_source("swissquote", isin, html)
    result = parse_quote_html(html, isin)
    normalized = result.product.model_dump()
    return models.upsert_product(
        normalized=normalized,
        raw_text=result.raw_html,
        source_kind=result.source_kind,
        source_file_path=None,
        source_file_hash_sha256=sha256_text(f"swissquote:{isin}"),
    )
