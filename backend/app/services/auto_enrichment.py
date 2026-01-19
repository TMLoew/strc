"""
Auto-enrichment service that runs continuously in the background.

Progressively enriches products with missing data, remembering position
between runs for seamless resumption.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Callable

from backend.app.services.finanzen_crawler_service import enrich_products_from_finanzen_batch
from backend.app.services.leonteq_pdf_enrichment import enrich_leonteq_products_batch
from backend.app.db.session import get_connection

logger = logging.getLogger(__name__)

# State file to track progress
STATE_FILE = Path("data/auto_enrich_state.json")


class AutoEnrichmentState:
    """Track auto-enrichment progress across runs."""

    def __init__(self):
        self.finanzen_offset = 0
        self.leonteq_offset = 0
        self.total_enriched = 0
        self.total_failed = 0
        self.last_run = None
        self.is_running = False

    def load(self) -> "AutoEnrichmentState":
        """Load state from disk."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.finanzen_offset = data.get("finanzen_offset", 0)
                self.leonteq_offset = data.get("leonteq_offset", 0)
                self.total_enriched = data.get("total_enriched", 0)
                self.total_failed = data.get("total_failed", 0)
                self.last_run = data.get("last_run")
                logger.info(f"Loaded auto-enrich state: finanzen={self.finanzen_offset}, leonteq={self.leonteq_offset}")
            except Exception as e:
                logger.warning(f"Could not load auto-enrich state: {e}")
        return self

    def save(self):
        """Save state to disk."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "finanzen_offset": self.finanzen_offset,
            "leonteq_offset": self.leonteq_offset,
            "total_enriched": self.total_enriched,
            "total_failed": self.total_failed,
            "last_run": time.time(),
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))
        logger.debug(f"Saved auto-enrich state: {data}")

    def reset(self):
        """Reset state to start from beginning."""
        self.finanzen_offset = 0
        self.leonteq_offset = 0
        self.total_enriched = 0
        self.total_failed = 0
        self.save()
        logger.info("Reset auto-enrich state")


def get_total_missing_coupons() -> int:
    """Get count of products missing coupon data."""
    query = """
        SELECT COUNT(*) as count
        FROM products
        WHERE isin IS NOT NULL
          AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
    """
    with get_connection() as conn:
        result = conn.execute(query).fetchone()
        return result["count"]


def get_enrichment_stats() -> dict:
    """
    Get comprehensive enrichment statistics.

    Returns counts of:
    - total_products: All products in database
    - fully_enriched: Products with all critical data populated
    - missing_coupon: Products missing coupon data
    - missing_underlyings: Products missing underlyings
    - missing_barrier: Barrier products missing barrier data
    """
    with get_connection() as conn:
        # Total products
        total = conn.execute("SELECT COUNT(*) as count FROM products WHERE isin IS NOT NULL").fetchone()["count"]

        # Products missing coupons (for coupon-bearing products)
        missing_coupon = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE isin IS NOT NULL
              AND (
                  product_type LIKE '%Reverse Convertible%'
                  OR product_type LIKE '%Express%'
                  OR product_type LIKE '%Credit Linked%'
                  OR product_type LIKE '%Coupon%'
              )
              AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
        """).fetchone()["count"]

        # Products missing underlyings (for structured products, not bonds)
        missing_underlyings = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE isin IS NOT NULL
              AND product_type NOT LIKE '%Bond%'
              AND product_type NOT LIKE '%Anleihe%'
              AND product_type NOT LIKE '%Obligation%'
              AND (
                  json_extract(normalized_json, '$.underlyings') IS NULL
                  OR json_type(json_extract(normalized_json, '$.underlyings')) != 'array'
                  OR json_array_length(json_extract(normalized_json, '$.underlyings')) = 0
              )
        """).fetchone()["count"]

        # Barrier products missing barrier data
        missing_barrier = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE isin IS NOT NULL
              AND (
                  product_type LIKE '%Barrier%'
                  OR product_type LIKE '%barrier%'
              )
              AND (
                  json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                  AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
              )
        """).fetchone()["count"]

        # Fully enriched = has critical data based on product type
        # For now, consider "fully enriched" as having:
        # 1. ISIN (already filtered)
        # 2. Coupon (if coupon product) OR underlyings (if structured product)
        # 3. Maturity date
        fully_enriched = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE isin IS NOT NULL
              AND maturity_date IS NOT NULL
              AND (
                  -- Has coupon data (for coupon products)
                  json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL
                  OR
                  -- Has underlyings (for structured products)
                  (
                      json_extract(normalized_json, '$.underlyings') IS NOT NULL
                      AND json_type(json_extract(normalized_json, '$.underlyings')) = 'array'
                      AND json_array_length(json_extract(normalized_json, '$.underlyings')) > 0
                  )
              )
        """).fetchone()["count"]

        return {
            "total_products": total,
            "fully_enriched": fully_enriched,
            "missing_coupon": missing_coupon,
            "missing_underlyings": missing_underlyings,
            "missing_barrier": missing_barrier,
            "incomplete": total - fully_enriched
        }


def run_auto_enrichment_cycle(
    state: AutoEnrichmentState,
    batch_size: int = 10,
    progress_callback: Callable = None
) -> dict:
    """
    Run one cycle of auto-enrichment.

    Args:
        state: Auto-enrichment state tracker
        batch_size: Number of products to process per cycle
        progress_callback: Optional callback(message, stats)

    Returns:
        Stats for this cycle
    """
    logger.info(f"Starting auto-enrich cycle (batch_size={batch_size})")

    cycle_stats = {
        "finanzen_enriched": 0,
        "finanzen_failed": 0,
        "leonteq_enriched": 0,
        "leonteq_failed": 0,
        "total_processed": 0,
    }

    # Phase 1: Finanzen.ch enrichment (faster, broader coverage) - CONCURRENT
    try:
        if progress_callback:
            progress_callback(f"Enriching {batch_size} products from finanzen.ch (concurrent)...", cycle_stats)

        # Get products with offset
        query = """
            SELECT id, isin, normalized_json
            FROM products
            WHERE isin IS NOT NULL
              AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """

        with get_connection() as conn:
            rows = conn.execute(query, (batch_size, state.finanzen_offset)).fetchall()

        if rows:
            # Process this batch concurrently with multiple workers
            from backend.app.services.finanzen_crawler_service import (
                enrich_product_from_finanzen,
            )
            from playwright.sync_api import sync_playwright

            # Thread-safe counters
            stats_lock = Lock()
            processed_count = [0]  # Mutable container for thread-safe updates

            def enrich_finanzen_worker(row_data):
                """Worker function to enrich a single product."""
                product_id, isin, normalized_json = row_data

                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context(
                            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                        )
                        page = context.new_page()

                        try:
                            success = enrich_product_from_finanzen(
                                page, product_id, isin, normalized_json or "{}"
                            )

                            # Update progress
                            with stats_lock:
                                processed_count[0] += 1
                                if progress_callback:
                                    progress_callback(
                                        f"Finanzen.ch: {processed_count[0]}/{len(rows)} ({isin})",
                                        cycle_stats
                                    )

                            # Small delay to be respectful
                            time.sleep(0.5)

                            return {"success": success, "isin": isin}

                        finally:
                            page.close()
                            context.close()
                            browser.close()

                except Exception as e:
                    logger.error(f"Worker error enriching {isin}: {e}")
                    return {"success": False, "isin": isin}

            # Use ThreadPoolExecutor to process products concurrently
            max_workers = min(3, len(rows))  # 3 concurrent workers
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_product = {
                    executor.submit(
                        enrich_finanzen_worker,
                        (row["id"], row["isin"], row["normalized_json"])
                    ): row["isin"]
                    for row in rows
                }

                # Process results as they complete
                for future in as_completed(future_to_product):
                    isin = future_to_product[future]
                    try:
                        result = future.result()

                        with stats_lock:
                            if result["success"]:
                                cycle_stats["finanzen_enriched"] += 1
                                state.total_enriched += 1
                            else:
                                cycle_stats["finanzen_failed"] += 1
                                state.total_failed += 1
                            cycle_stats["total_processed"] += 1

                    except Exception as e:
                        logger.error(f"Failed to get result for {isin}: {e}")
                        with stats_lock:
                            cycle_stats["finanzen_failed"] += 1
                            state.total_failed += 1

            # Update offset
            state.finanzen_offset += len(rows)
            state.save()

        else:
            logger.info("No more products to enrich from finanzen.ch")
            # Reset offset to cycle back to beginning
            state.finanzen_offset = 0
            state.save()

    except Exception as e:
        logger.error(f"Auto-enrich finanzen.ch failed: {e}", exc_info=True)

    # Phase 2: Leonteq PDF enrichment - DISABLED (high failure rate, termsheet links not found)
    # Most Leonteq products don't have accessible PDF download links on their pages
    # Keeping code commented for future investigation
    if False:  # Disabled - termsheet links not found
        try:
            if progress_callback:
                progress_callback(f"Checking for Leonteq products to enrich...", cycle_stats)

            # Get products missing underlyings (priority for Leonteq enrichment)
            query_leonteq = """
                SELECT id, isin, normalized_json, raw_text, source_kind
                FROM products
                WHERE isin IS NOT NULL
                  AND (json_type(normalized_json, '$.underlyings') IS NULL
                       OR json_array_length(normalized_json, '$.underlyings') = 0)
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """

            with get_connection() as conn:
                leonteq_rows = conn.execute(query_leonteq, (min(batch_size, 5), state.leonteq_offset)).fetchall()

            if leonteq_rows:
                # Try to enrich these products from Leonteq PDFs
                from backend.app.services.leonteq_session_service import get_leonteq_session_state

                storage_state = get_leonteq_session_state()

                if storage_state:
                    logger.info(f"Enriching {len(leonteq_rows)} products from Leonteq PDFs (concurrent)")

                    if progress_callback:
                        progress_callback(
                            f"Leonteq: Enriching {len(leonteq_rows)} products with underlyings (concurrent)...",
                            cycle_stats
                        )

                    # Enrich using Leonteq PDF enrichment - CONCURRENT
                    from backend.app.services.leonteq_pdf_enrichment import enrich_product_from_pdf
                    from playwright.sync_api import sync_playwright

                    # Thread-safe counters
                    leonteq_stats_lock = Lock()
                    leonteq_processed_count = [0]

                    def enrich_leonteq_worker(row_data):
                        """Worker function to enrich a single product from Leonteq PDF."""
                        product_id, isin, raw_text, normalized_json = row_data

                        try:
                            with sync_playwright() as p:
                                browser = p.chromium.launch(headless=True)
                                context = browser.new_context(storage_state=storage_state)
                                page = context.new_page()

                                try:
                                    # Enrich from Leonteq PDF
                                    success = enrich_product_from_pdf(
                                        page,
                                        product_id,
                                        raw_text or "{}",
                                        normalized_json or "{}"
                                    )

                                    # Update progress
                                    with leonteq_stats_lock:
                                        leonteq_processed_count[0] += 1
                                        if progress_callback:
                                            progress_callback(
                                                f"Leonteq: {leonteq_processed_count[0]}/{len(leonteq_rows)} ({isin})",
                                                cycle_stats
                                            )

                                    # Small delay to avoid rate limiting
                                    time.sleep(1)

                                    return {"success": success, "isin": isin}

                                finally:
                                    page.close()
                                    context.close()
                                    browser.close()

                        except Exception as e:
                            logger.error(f"Worker error enriching {isin} from Leonteq: {e}")
                            return {"success": False, "isin": isin}

                    # Use ThreadPoolExecutor to process products concurrently
                    max_workers = min(2, len(leonteq_rows))  # 2 concurrent workers for Leonteq (rate limiting)
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submit all tasks
                        future_to_product = {
                            executor.submit(
                                enrich_leonteq_worker,
                                (row["id"], row["isin"], row["raw_text"], row["normalized_json"])
                            ): row["isin"]
                            for row in leonteq_rows
                        }

                        # Process results as they complete
                        for future in as_completed(future_to_product):
                            isin = future_to_product[future]
                            try:
                                result = future.result()

                                with leonteq_stats_lock:
                                    if result["success"]:
                                        cycle_stats["leonteq_enriched"] += 1
                                        state.total_enriched += 1
                                    else:
                                        cycle_stats["leonteq_failed"] += 1
                                        state.total_failed += 1
                                    cycle_stats["total_processed"] += 1

                            except Exception as e:
                                logger.error(f"Failed to get result for {isin}: {e}")
                                with leonteq_stats_lock:
                                    cycle_stats["leonteq_failed"] += 1
                                    state.total_failed += 1

                    # Update offset
                    state.leonteq_offset += len(leonteq_rows)
                    state.save()
                else:
                    logger.info("No Leonteq session available, skipping Leonteq enrichment")
                    if progress_callback:
                        progress_callback("Skipping Leonteq enrichment (no session)", cycle_stats)

            else:
                logger.info("No more products to enrich from Leonteq")
                # Reset offset to cycle back to beginning
                state.leonteq_offset = 0
                state.save()

        except Exception as e:
            logger.error(f"Auto-enrich Leonteq failed: {e}", exc_info=True)

    logger.info(f"Auto-enrich cycle complete: {cycle_stats}")
    return cycle_stats


def run_auto_enrichment_continuous(
    batch_size: int = 10,
    delay_seconds: int = 30,
    progress_callback: Callable = None,
    stop_callback: Callable = None
):
    """
    Run auto-enrichment continuously until stopped.

    Args:
        batch_size: Products to process per cycle
        delay_seconds: Delay between cycles
        progress_callback: Optional callback(message, stats)
        stop_callback: Optional callback() -> bool that returns True to stop
    """
    state = AutoEnrichmentState().load()
    state.is_running = True

    logger.info(f"Starting continuous auto-enrichment (batch={batch_size}, delay={delay_seconds}s)")

    try:
        while True:
            # Check if we should stop
            if stop_callback and stop_callback():
                logger.info("Auto-enrichment stopped by callback")
                break

            # Run one cycle
            cycle_stats = run_auto_enrichment_cycle(
                state, batch_size, progress_callback
            )

            # Check if we made progress
            if cycle_stats["total_processed"] == 0:
                logger.info("No products to enrich, waiting...")
                if progress_callback:
                    progress_callback("Waiting for products to enrich...", cycle_stats)
                time.sleep(delay_seconds * 2)  # Wait longer if nothing to do
                continue

            # Delay before next cycle
            if progress_callback:
                progress_callback(
                    f"Cycle complete. Waiting {delay_seconds}s before next cycle...",
                    cycle_stats
                )
            time.sleep(delay_seconds)

    except KeyboardInterrupt:
        logger.info("Auto-enrichment interrupted by user")
    except Exception as e:
        logger.error(f"Auto-enrichment error: {e}", exc_info=True)
    finally:
        state.is_running = False
        state.save()
        logger.info(f"Auto-enrichment stopped. Total enriched: {state.total_enriched}")
