"""
Auto-enrichment service that runs continuously in the background.

Progressively enriches products with missing data, remembering position
between runs for seamless resumption.
"""

import json
import logging
import time
from pathlib import Path
from typing import Callable

from backend.app.services.finanzen_crawler_service import enrich_products_from_finanzen_batch
from backend.app.services.leonteq_pdf_enrichment import enrich_leonteq_products_batch
from backend.app.db.session import get_connection, init_db

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

    # Phase 1: Finanzen.ch enrichment (faster, broader coverage)
    try:
        if progress_callback:
            progress_callback(f"Enriching {batch_size} products from finanzen.ch...", cycle_stats)

        # Get products with offset
        init_db()
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
            # Process this batch
            from backend.app.services.finanzen_crawler_service import (
                enrich_product_from_finanzen,
            )
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                )
                page = context.new_page()

                try:
                    for idx, row in enumerate(rows):
                        product_id = row["id"]
                        isin = row["isin"]
                        normalized_json = row["normalized_json"] or "{}"

                        if progress_callback:
                            progress_callback(
                                f"Finanzen.ch: {idx + 1}/{len(rows)} ({isin})",
                                cycle_stats
                            )

                        success = enrich_product_from_finanzen(
                            page, product_id, isin, normalized_json
                        )

                        if success:
                            cycle_stats["finanzen_enriched"] += 1
                            state.total_enriched += 1
                        else:
                            cycle_stats["finanzen_failed"] += 1
                            state.total_failed += 1

                        cycle_stats["total_processed"] += 1

                        # Small delay to be respectful
                        time.sleep(1)

                finally:
                    page.close()
                    context.close()
                    browser.close()

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
