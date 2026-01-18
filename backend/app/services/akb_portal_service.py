from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

from backend.app.db import models
from backend.app.settings import settings
from core.models import make_field
from core.utils.hashing import sha256_text
from core.sources.akb_finanzportal import (
    extract_listings,
    fetch_detail_html,
    multi_search,
    parse_detail_html,
    total_hits,
)


def crawl_akb_portal_catalog(run_id: str | None = None) -> dict[str, list]:
    prefixes = deque(["CH"])
    seen_listings: set[str] = set()
    ids: list[str] = []
    errors: list[dict[str, str]] = []
    lock = Lock()

    def process_listing(listing):
        if listing.listing_id in seen_listings:
            return
        seen_listings.add(listing.listing_id)
        try:
            html = fetch_detail_html(listing.listing_id)
            product = parse_detail_html(html, listing.listing_id)
            if (not product.isin.value) and listing.isin:
                product.isin = make_field(listing.isin, 0.6, "akb_multi_search")
            if (not product.product_name.value) and listing.name:
                product.product_name = make_field(listing.name, 0.5, "akb_multi_search")
            if (not product.ticker_six.value) and listing.symbol:
                product.ticker_six = make_field(listing.symbol, 0.5, "akb_multi_search")
            if (not product.currency.value) and listing.currency:
                product.currency = make_field(listing.currency, 0.5, "akb_multi_search")
            if (not product.listing_venue.value) and listing.market:
                product.listing_venue = make_field(listing.market, 0.5, "akb_multi_search")

            product_id = models.upsert_product(
                normalized=product.model_dump(),
                raw_text=html,
                source_kind="akb_finanzportal",
                source_file_path=None,
                source_file_hash_sha256=sha256_text(f"akb_portal:{listing.listing_id}"),
            )
            with lock:
                ids.append(product_id)
            isin_value = product.isin.value
            if run_id:
                models.increment_crawl_completed(run_id)
        except Exception as exc:
            with lock:
                errors.append(
                    {
                        "listing_id": listing.listing_id,
                        "source": "akb_detail",
                        "error": str(exc),
                    }
                )
            if run_id:
                models.increment_crawl_errors(run_id, f"akb_detail:{listing.listing_id}:{exc}")
            return

        if not isin_value:
            return

        # Skip enrichment if disabled (much faster, fewer errors)
        if not settings.enable_akb_enrichment:
            return

        try:
            from backend.app.services.leonteq_service import ingest_leonteq_isin

            product_id = ingest_leonteq_isin(isin_value)
            with lock:
                ids.append(product_id)
        except Exception as exc:
            with lock:
                errors.append({"isin": isin_value, "source": "leonteq", "error": str(exc)})
            if run_id:
                models.increment_crawl_errors(run_id, f"leonteq:{isin_value}:{exc}")

        try:
            from backend.app.services.swissquote_service import ingest_swissquote_isin

            product_id = ingest_swissquote_isin(isin_value)
            if product_id:
                with lock:
                    ids.append(product_id)
        except Exception as exc:
            with lock:
                errors.append({"isin": isin_value, "source": "swissquote", "error": str(exc)})
            if run_id:
                models.increment_crawl_errors(run_id, f"swissquote:{isin_value}:{exc}")

        if settings.enable_yahoo_enrich:
            try:
                from backend.app.services.yahoo_service import ingest_yahoo_isin

                yahoo_id = ingest_yahoo_isin(isin_value)
                if yahoo_id:
                    with lock:
                        ids.append(yahoo_id)
            except Exception as exc:
                with lock:
                    errors.append({"isin": isin_value, "source": "yahoo", "error": str(exc)})
                if run_id:
                    models.increment_crawl_errors(run_id, f"yahoo:{isin_value}:{exc}")

    with ThreadPoolExecutor(max_workers=settings.crawl_max_workers) as executor:
        futures = []
        while prefixes:
            # Check if crawl has been cancelled
            if run_id and models.is_crawl_cancelled(run_id):
                # Cancel pending futures
                for future in futures:
                    future.cancel()
                return {"ids": ids, "errors": errors}

            # Check if crawl is paused
            if run_id:
                while models.is_crawl_paused(run_id):
                    time.sleep(1)
                    # Check if cancelled while paused
                    if models.is_crawl_cancelled(run_id):
                        for future in futures:
                            future.cancel()
                        return {"ids": ids, "errors": errors}

            prefix = prefixes.popleft()
            try:
                response = multi_search(prefix)
            except Exception as exc:
                errors.append({"prefix": prefix, "source": "akb_multi_search", "error": str(exc)})
                if run_id:
                    models.increment_crawl_errors(run_id, f"akb_multi_search:{prefix}:{exc}")
                continue

            listings = extract_listings(response)
            hits = total_hits(response)
            if run_id and prefix == "CH" and hits:
                models.update_crawl_run(run_id, total=hits)
            if hits > len(listings) and len(prefix) < 12:
                for next_char in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    prefixes.append(prefix + next_char)
                continue

            for listing in listings:
                if listing.listing_id in seen_listings:
                    continue
                futures.append(executor.submit(process_listing, listing))

        for future in as_completed(futures):
            future.result()

    if run_id:
        models.update_crawl_run(run_id, status="completed")
    return {"ids": ids, "errors": errors}
