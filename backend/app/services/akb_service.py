from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from backend.app.db import models
from backend.app.settings import settings
from core.models import NormalizedProduct, make_field
from core.sources.akb import fetch_akb_html, parse_akb_isins
from core.utils.hashing import sha256_text


def crawl_akb_catalog(run_id: str | None = None) -> dict[str, list]:
    """
    Crawl AKB catalog page and extract ISINs.

    Args:
        run_id: Optional crawl run ID for progress tracking

    Returns:
        Dictionary with 'ids' (list of product IDs) and 'errors' (list of error dicts)
    """
    ids: list[str] = []
    errors: list[dict[str, str]] = []
    lock = Lock()

    try:
        # Fetch catalog HTML
        print("AKB catalog crawl: Fetching catalog page...")
        html = fetch_akb_html()
        isins = parse_akb_isins(html)

        print(f"AKB catalog crawl: Found {len(isins)} ISINs")

        # Update total count
        if run_id:
            models.update_crawl_run(run_id, total=len(isins))

        # Process each ISIN
        def process_isin(isin: str):
            """Process a single ISIN from catalog."""
            try:
                product = NormalizedProduct()
                product.isin = make_field(isin, 0.6, "akb_html")
                normalized = product.model_dump()
                product_id = models.upsert_product(
                    normalized=normalized,
                    raw_text=html,
                    source_kind="akb_html",
                    source_file_path=None,
                    source_file_hash_sha256=sha256_text(f"akb:{isin}"),
                )

                with lock:
                    ids.append(product_id)

                if run_id:
                    models.increment_crawl_completed(run_id)

            except Exception as exc:
                with lock:
                    errors.append({
                        "isin": isin,
                        "source": "akb_html",
                        "error": str(exc)
                    })

                if run_id:
                    models.increment_crawl_errors(run_id, f"akb_html:{isin}:{exc}")

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=settings.crawl_max_workers) as executor:
            futures = [executor.submit(process_isin, isin) for isin in isins]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass  # Already handled in process_isin

        # Mark crawl as completed
        if run_id:
            models.update_crawl_run(run_id, status="completed")

        print(f"AKB catalog crawl completed: {len(ids)} products stored, {len(errors)} errors")

    except Exception as exc:
        # Mark crawl as failed
        if run_id:
            models.update_crawl_run(run_id, status="failed", last_error=str(exc))
        print(f"AKB catalog crawl failed: {exc}")
        raise

    return {"ids": ids, "errors": errors}


def crawl_akb_enrich(run_id: str | None = None) -> dict[str, list]:
    """
    Crawl AKB catalog and enrich with data from Leonteq, Swissquote, and Yahoo.

    Args:
        run_id: Optional crawl run ID for progress tracking

    Returns:
        Dictionary with 'ids' (list of product IDs) and 'errors' (list of error dicts)
    """
    ids: list[str] = []
    errors: list[dict[str, str]] = []
    lock = Lock()

    try:
        # Fetch catalog HTML
        print("AKB enrich crawl: Fetching catalog page...")
        html = fetch_akb_html()
        isins = parse_akb_isins(html)

        print(f"AKB enrich crawl: Found {len(isins)} ISINs, will enrich from multiple sources")

        # Update total count (multiply by sources to enrich)
        sources_count = 2  # leonteq + swissquote
        if settings.enable_yahoo_enrich:
            sources_count += 1
        if run_id:
            models.update_crawl_run(run_id, total=len(isins) * sources_count)

        # Process each ISIN with enrichment
        def process_isin_with_enrich(isin: str):
            """Process a single ISIN and enrich from multiple sources."""
            # 1. Store AKB catalog entry
            try:
                product = NormalizedProduct()
                product.isin = make_field(isin, 0.6, "akb_html")
                normalized = product.model_dump()
                product_id = models.upsert_product(
                    normalized=normalized,
                    raw_text=html,
                    source_kind="akb_html",
                    source_file_path=None,
                    source_file_hash_sha256=sha256_text(f"akb:{isin}"),
                )

                with lock:
                    ids.append(product_id)

                if run_id:
                    models.increment_crawl_completed(run_id)

            except Exception as exc:
                with lock:
                    errors.append({"isin": isin, "source": "akb_html", "error": str(exc)})
                if run_id:
                    models.increment_crawl_errors(run_id, f"akb_html:{isin}:{exc}")

            # 2. Enrich with Leonteq
            try:
                from backend.app.services.leonteq_service import ingest_leonteq_isin

                leonteq_id = ingest_leonteq_isin(isin)
                with lock:
                    ids.append(leonteq_id)

                if run_id:
                    models.increment_crawl_completed(run_id)

            except Exception as exc:
                with lock:
                    errors.append({"isin": isin, "source": "leonteq", "error": str(exc)})
                if run_id:
                    models.increment_crawl_errors(run_id, f"leonteq:{isin}:{exc}")

            # 3. Enrich with Swissquote
            try:
                from backend.app.services.swissquote_service import ingest_swissquote_isin

                swissquote_id = ingest_swissquote_isin(isin)
                if swissquote_id:
                    with lock:
                        ids.append(swissquote_id)

                if run_id:
                    models.increment_crawl_completed(run_id)

            except Exception as exc:
                with lock:
                    errors.append({"isin": isin, "source": "swissquote", "error": str(exc)})
                if run_id:
                    models.increment_crawl_errors(run_id, f"swissquote:{isin}:{exc}")

            # 4. Enrich with Yahoo (if enabled)
            if settings.enable_yahoo_enrich:
                try:
                    from backend.app.services.yahoo_service import ingest_yahoo_isin

                    yahoo_id = ingest_yahoo_isin(isin)
                    if yahoo_id:
                        with lock:
                            ids.append(yahoo_id)

                    if run_id:
                        models.increment_crawl_completed(run_id)

                except Exception as exc:
                    with lock:
                        errors.append({"isin": isin, "source": "yahoo", "error": str(exc)})
                    if run_id:
                        models.increment_crawl_errors(run_id, f"yahoo:{isin}:{exc}")

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=settings.crawl_max_workers) as executor:
            futures = [executor.submit(process_isin_with_enrich, isin) for isin in isins]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass  # Already handled in process_isin_with_enrich

        # Mark crawl as completed
        if run_id:
            models.update_crawl_run(run_id, status="completed")

        print(f"AKB enrich crawl completed: {len(ids)} products stored, {len(errors)} errors")

    except Exception as exc:
        # Mark crawl as failed
        if run_id:
            models.update_crawl_run(run_id, status="failed", last_error=str(exc))
        print(f"AKB enrich crawl failed: {exc}")
        raise

    return {"ids": ids, "errors": errors}
