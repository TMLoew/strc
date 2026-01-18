from __future__ import annotations

from backend.app.db import models
from backend.app.settings import settings
from backend.app.services.swissquote_session_service import get_session_state
from core.utils.hashing import sha256_text
from core.models import NormalizedProduct, make_field
from core.sources.swissquote_scanner import (
    extract_isins,
    fetch_scanner_html,
    fetch_scanner_html_fallback,
    fetch_scanner_isins,
)


def crawl_swissquote_scanner(
    run_id: str | None = None,
    *,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, list]:
    errors: list[dict[str, str]] = []
    html = None
    try:
        isins = fetch_scanner_isins(
            username=username or settings.swissquote_username,
            password=password or settings.swissquote_password,
            storage_state=get_session_state(),
        )
    except Exception as exc:
        errors.append({"source": "swissquote_scanner", "error": str(exc)})
        if run_id:
            models.increment_crawl_errors(run_id, f"swissquote_scanner:{exc}")
        try:
            html = fetch_scanner_html()
        except Exception as html_exc:
            errors.append({"source": "swissquote_scanner", "error": str(html_exc)})
            if run_id:
                models.increment_crawl_errors(run_id, f"swissquote_scanner:{html_exc}")
            html = fetch_scanner_html_fallback()
        isins = extract_isins(html)
    if run_id:
        models.update_crawl_run(run_id, total=len(isins))
    ids: list[str] = []

    if not isins:
        errors.append({"source": "swissquote_scanner", "error": "no_isins_found"})
        if run_id:
            models.increment_crawl_errors(run_id, "swissquote_scanner:no_isins_found")

    for isin in isins:
        product = NormalizedProduct()
        product.isin = make_field(isin, 0.5, "swissquote_scanner")
        product_id = models.upsert_product(
            normalized=product.model_dump(),
            raw_text=html,
            source_kind="swissquote_scanner",
            source_file_path=None,
            source_file_hash_sha256=sha256_text(f"swissquote_scanner:{isin}"),
        )
        ids.append(product_id)
        if run_id:
            models.increment_crawl_completed(run_id)

        try:
            from backend.app.services.leonteq_service import ingest_leonteq_isin

            ids.append(ingest_leonteq_isin(isin))
        except Exception as exc:
            errors.append({"isin": isin, "source": "leonteq", "error": str(exc)})
            if run_id:
                models.increment_crawl_errors(run_id, f"leonteq:{isin}:{exc}")

        try:
            from backend.app.services.swissquote_service import ingest_swissquote_isin

            product_id = ingest_swissquote_isin(isin)
            if product_id:
                ids.append(product_id)
        except Exception as exc:
            errors.append({"isin": isin, "source": "swissquote", "error": str(exc)})
            if run_id:
                models.increment_crawl_errors(run_id, f"swissquote:{isin}:{exc}")

        if settings.enable_yahoo_enrich:
            try:
                from backend.app.services.yahoo_service import ingest_yahoo_isin

                yahoo_id = ingest_yahoo_isin(isin)
                if yahoo_id:
                    ids.append(yahoo_id)
            except Exception as exc:
                errors.append({"isin": isin, "source": "yahoo", "error": str(exc)})
                if run_id:
                    models.increment_crawl_errors(run_id, f"yahoo:{isin}:{exc}")

    if run_id:
        models.update_crawl_run(run_id, status="completed")
    return {"ids": ids, "errors": errors}
