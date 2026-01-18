"""
Service to crawl finanzen.ch for structured product data.

Uses browser automation to bypass 403 blocks and extract comprehensive data
including coupon rates, barriers, strikes, and other fields.
"""

import json
import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

from backend.app.db import models
from core.sources.finanzen import parse_html
from core.utils.hashing import sha256_text

logger = logging.getLogger(__name__)

FINANZEN_BASE_URL = "https://www.finanzen.ch/derivate"


def fetch_product_with_browser(page: Page, isin: str) -> str | None:
    """
    Fetch product page HTML using browser automation.

    Args:
        page: Playwright page instance
        isin: Product ISIN

    Returns:
        HTML content or None if failed
    """
    try:
        url = f"{FINANZEN_BASE_URL}/{isin.lower()}"
        logger.debug(f"Navigating to {url}")

        page.goto(url, wait_until="networkidle", timeout=15000)
        time.sleep(1)  # Wait for any dynamic content

        html = page.content()

        # Check if we got a valid product page (not 404/error)
        if "nicht gefunden" in html.lower() or "not found" in html.lower():
            logger.warning(f"ISIN {isin}: Product not found on finanzen.ch")
            return None

        logger.debug(f"ISIN {isin}: Successfully fetched page ({len(html)} bytes)")
        return html

    except PlaywrightTimeout:
        logger.warning(f"ISIN {isin}: Timeout loading page")
        return None
    except Exception as e:
        logger.error(f"ISIN {isin}: Failed to fetch page: {e}")
        return None


def enrich_product_from_finanzen(
    page: Page,
    product_id: int,
    isin: str,
    normalized_json: str,
    progress_callback: callable = None
) -> bool:
    """
    Fetch finanzen.ch data, parse it, and update product in database.

    Args:
        page: Authenticated Playwright page
        product_id: Product database ID
        isin: Product ISIN
        normalized_json: Current normalized data
        progress_callback: Optional callback(message)

    Returns:
        True if enrichment succeeded, False otherwise
    """
    # Extract product name for display
    product_name = None
    try:
        data = json.loads(normalized_json) if normalized_json else {}
        product_name = data.get("product_name", {}).get("value")
    except json.JSONDecodeError as e:
        logger.warning(f"Product {product_id} ({isin}): Invalid JSON in normalized_json: {e}")
    except Exception as e:
        logger.warning(f"Product {product_id} ({isin}): Error extracting product name: {e}")

    display_name = product_name if product_name else isin

    try:
        if progress_callback:
            progress_callback(message=f"Fetching data for {display_name}")

        # Fetch HTML with browser
        html = fetch_product_with_browser(page, isin)
        if not html:
            logger.debug(f"Product {product_id} ({isin}): No HTML fetched")
            return False

        if progress_callback:
            progress_callback(message=f"Parsing {display_name}")

        # Parse HTML
        result = parse_html(html, isin)
        finanzen_data = result.product.model_dump()

        # Merge with existing data
        try:
            existing_data = json.loads(normalized_json) if normalized_json else {}
        except json.JSONDecodeError as e:
            logger.error(f"Product {product_id} ({isin}): Cannot parse existing normalized_json, starting fresh: {e}")
            existing_data = {}

        # Fields to potentially update from finanzen.ch
        fields_to_merge = [
            "isin", "issuer_name", "currency", "product_name", "product_type",
            "coupon_rate_pct_pa",  # CRITICAL
            "strike_price",
            "cap_level_pct",
            "participation_rate_pct",
            "maturity_date",
            "issue_date",
            "underlyings",  # Contains barrier data
        ]

        updates_made = False
        for field in fields_to_merge:
            finanzen_value = finanzen_data.get(field)

            # Skip if finanzen has no data for this field
            if not finanzen_value:
                continue

            # For Field types (dict with value/confidence)
            if isinstance(finanzen_value, dict) and "value" in finanzen_value:
                existing_field = existing_data.get(field, {})
                existing_value = existing_field.get("value") if isinstance(existing_field, dict) else None
                existing_confidence = existing_field.get("confidence", 0) if isinstance(existing_field, dict) else 0
                finanzen_confidence = finanzen_value.get("confidence", 0)

                # Update if field is missing or finanzen has better confidence
                if not existing_value or finanzen_confidence > existing_confidence:
                    existing_data[field] = finanzen_value
                    updates_made = True
                    logger.debug(f"Product {product_id}: Updated {field} = {finanzen_value.get('value')}")

            # For list fields (underlyings)
            elif isinstance(finanzen_value, list) and finanzen_value:
                existing_field = existing_data.get(field, [])
                # If existing is empty or finanzen has more data, update
                if not existing_field or len(finanzen_value) > len(existing_field):
                    existing_data[field] = finanzen_value
                    updates_made = True
                    logger.debug(f"Product {product_id}: Updated {field} (list)")

        if updates_made:
            # Update database
            updated_json = json.dumps(existing_data)
            models.update_product_normalized_json(product_id, updated_json)

            # Also update raw_text if we don't have it
            product = models.get_product(product_id)
            if not product.get("raw_text"):
                models.update_product_raw_text(product_id, html)

            logger.info(f"Product {product_id} ({isin}): Enriched with finanzen.ch data")
            return True
        else:
            logger.debug(f"Product {product_id} ({isin}): No new data from finanzen.ch")
            return False

    except Exception as e:
        logger.error(f"Product {product_id} ({isin}): Enrichment failed: {e}")
        return False


def enrich_products_from_finanzen_batch(
    limit: int = 100,
    progress_callback: callable = None,
    checkpoint_file: Path | None = None,
    filter_mode: str = "missing_any"
) -> dict[str, int]:
    """
    Enrich multiple products by fetching data from finanzen.ch.

    Args:
        limit: Maximum products to process
        progress_callback: Optional callback(current, total, message, stats)
        checkpoint_file: Optional checkpoint file for resume capability
        filter_mode: What products to target:
            - "missing_any": Products missing coupons OR barriers (default)
            - "missing_coupon": Only products missing coupon rates
            - "missing_barrier": Only products missing barrier data
            - "all_with_isin": All products that have ISINs

    Returns:
        Statistics: {"processed": N, "enriched": M, "failed": K, "skipped": S}
    """
    logger.info(f"Starting finanzen.ch batch enrichment (limit={limit}, filter={filter_mode})")

    # Load checkpoint if exists
    start_offset = 0
    if checkpoint_file and checkpoint_file.exists():
        try:
            checkpoint_data = json.loads(checkpoint_file.read_text())
            start_offset = checkpoint_data.get("processed", 0)
            logger.info(f"Resuming from checkpoint: {start_offset} products already processed")
        except Exception as e:
            logger.warning(f"Could not load checkpoint: {e}")

    # Get products from database - need products with ISINs
    # Build query based on filter mode
    from backend.app.db.session import get_connection, init_db

    init_db()

    # Build WHERE clause based on filter mode
    if filter_mode == "missing_coupon":
        where_clause = """
            WHERE isin IS NOT NULL
              AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
        """
    elif filter_mode == "missing_barrier":
        where_clause = """
            WHERE isin IS NOT NULL
              AND (
                json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
              )
        """
    elif filter_mode == "all_with_isin":
        where_clause = """
            WHERE isin IS NOT NULL
        """
    else:  # "missing_any" (default)
        where_clause = """
            WHERE isin IS NOT NULL
              AND (
                json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
                OR json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
              )
        """

    query = f"""
        SELECT id, isin, normalized_json
        FROM products
        {where_clause}
        ORDER BY updated_at DESC
        LIMIT ?
    """

    with get_connection() as conn:
        rows = conn.execute(query, (limit + start_offset,)).fetchall()

    # Convert to list of dicts
    products_with_isin = [
        {
            "id": row["id"],
            "isin": row["isin"],
            "normalized_json": row["normalized_json"] or "{}"
        }
        for row in rows
    ]

    # Skip already processed
    products = products_with_isin[start_offset:]
    total = len(products)

    if total == 0:
        logger.info("No products need finanzen.ch enrichment")
        return {"processed": 0, "enriched": 0, "failed": 0, "skipped": 0}

    logger.info(f"Found {total} products to process")

    stats = {"processed": start_offset, "enriched": 0, "failed": 0, "skipped": 0}

    # Initialize browser
    logger.info("Initializing browser...")
    if progress_callback:
        progress_callback(0, total, "Initializing browser...", stats)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = context.new_page()

        logger.info("Browser initialized")

        try:
            for idx, product in enumerate(products):
                product_id = product["id"]
                isin = product["isin"]
                normalized_json = product["normalized_json"]

                # Extract product name for display
                product_name = None
                try:
                    data = json.loads(normalized_json) if normalized_json else {}
                    product_name = data.get("product_name", {}).get("value")
                except json.JSONDecodeError as e:
                    logger.warning(f"Product {product_id} ({isin}): Invalid JSON in normalized_json: {e}")
                except Exception as e:
                    logger.warning(f"Product {product_id} ({isin}): Error extracting product name: {e}")

                display_name = product_name if product_name else isin

                stats["processed"] += 1
                current = idx + 1

                if progress_callback:
                    progress_callback(current, total, f"Processing {display_name} ({current}/{total})", stats)

                logger.info(f"[{current}/{total}] Processing {display_name} ({isin})")

                success = enrich_product_from_finanzen(
                    page,
                    product_id,
                    isin,
                    normalized_json,
                    progress_callback=lambda message: progress_callback(current, total, message, stats) if progress_callback else None
                )

                if success:
                    stats["enriched"] += 1
                else:
                    stats["failed"] += 1

                # Save checkpoint every 10 products
                if checkpoint_file and stats["processed"] % 10 == 0:
                    checkpoint_data = {
                        "processed": stats["processed"],
                        "enriched": stats["enriched"],
                        "failed": stats["failed"],
                        "timestamp": time.time()
                    }
                    checkpoint_file.write_text(json.dumps(checkpoint_data, indent=2))
                    logger.debug(f"Checkpoint saved: {stats['processed']} processed")

                # Progress logging
                if stats["processed"] % 10 == 0:
                    logger.info(f"Progress: {stats['processed']}/{total + start_offset} processed, {stats['enriched']} enriched, {stats['failed']} failed")

                # Small delay to avoid rate limiting
                time.sleep(2)

        finally:
            page.close()
            context.close()
            browser.close()

    # Clear checkpoint on completion
    if checkpoint_file and checkpoint_file.exists():
        checkpoint_file.unlink()
        logger.info("Checkpoint cleared (enrichment complete)")

    logger.info(f"Batch enrichment complete: {stats}")
    return stats
