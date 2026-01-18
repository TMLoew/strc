"""
Service to enrich Leonteq API products with data extracted from termsheet PDFs.

PDFs are downloaded temporarily via authenticated browser, parsed, and immediately deleted.
Only extracted structured data is saved to the database.
"""

import json
import logging
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Download

from backend.app.db import models
from backend.app.settings import settings
from core.sources.leonteq import interactive_login_storage_state
from core.sources.pdf_termsheet import extract_text, parse_pdf

# State file for tracking manual Leonteq enrichment progress
LEONTEQ_STATE_FILE = Path("data/leonteq_enrich_state.json")

logger = logging.getLogger(__name__)

LEONTEQ_BASE_URL = "https://structuredproducts-ch.leonteq.com"


def load_leonteq_state() -> dict:
    """Load Leonteq enrichment state from disk."""
    if LEONTEQ_STATE_FILE.exists():
        try:
            return json.loads(LEONTEQ_STATE_FILE.read_text())
        except Exception as e:
            logger.warning(f"Could not load Leonteq state: {e}")
    return {"offset": 0, "total_enriched": 0, "total_failed": 0}


def save_leonteq_state(offset: int, total_enriched: int, total_failed: int):
    """Save Leonteq enrichment state to disk."""
    LEONTEQ_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "offset": offset,
        "total_enriched": total_enriched,
        "total_failed": total_failed,
        "last_run": time.time()
    }
    LEONTEQ_STATE_FILE.write_text(json.dumps(state, indent=2))
    logger.debug(f"Saved Leonteq state: offset={offset}")


def reset_leonteq_state():
    """Reset Leonteq enrichment state to start from beginning."""
    if LEONTEQ_STATE_FILE.exists():
        LEONTEQ_STATE_FILE.unlink()
    logger.info("Reset Leonteq enrichment state")


def get_isin_from_raw_text(raw_text: str) -> str | None:
    """Extract ISIN from Leonteq API raw_text."""
    try:
        data = json.loads(raw_text)
        isin = data.get("identifiers", {}).get("isin")
        return isin
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def download_termsheet_pdf_from_product_page(page: Page, isin: str) -> Path | None:
    """
    Navigate to product page and download English termsheet PDF.

    Returns path to downloaded PDF, or None if download failed.
    """
    try:
        product_url = f"{LEONTEQ_BASE_URL}/isin/{isin}"
        logger.debug(f"Navigating to {product_url}")

        page.goto(product_url, wait_until="networkidle", timeout=30000)
        time.sleep(2)  # Wait for JavaScript to load

        # Look for English termsheet link
        # Try multiple possible selectors
        selectors = [
            'a[href*="termsheet"][href*="en.pdf"]',
            'a:has-text("Termsheet"):has-text("EN")',
            'a:has-text("Termsheet (EN)")',
            'button:has-text("Termsheet"):has-text("EN")',
        ]

        download_element = None
        for selector in selectors:
            try:
                download_element = page.query_selector(selector)
                if download_element:
                    logger.debug(f"Found termsheet link with selector: {selector}")
                    break
            except Exception:
                continue

        if not download_element:
            logger.warning(f"ISIN {isin}: Could not find termsheet download link")
            return None

        # Download PDF
        with page.expect_download(timeout=30000) as download_info:
            download_element.click()

        download: Download = download_info.value

        # Save to temporary file
        temp_pdf = Path(tempfile.mkdtemp()) / f"termsheet-{isin}.pdf"
        download.save_as(temp_pdf)

        logger.info(f"ISIN {isin}: Downloaded PDF to {temp_pdf}")
        return temp_pdf

    except Exception as e:
        logger.error(f"ISIN {isin}: Failed to download PDF: {e}")
        return None


def enrich_product_from_pdf(
    page: Page,
    product_id: int,
    raw_text: str,
    normalized_json: str,
    progress_callback: callable = None
) -> bool:
    """
    Download termsheet PDF from product page, extract data, update product, and delete PDF.

    Args:
        page: Authenticated Playwright page
        product_id: Product database ID
        raw_text: Raw JSON from Leonteq API
        normalized_json: Current normalized data
        progress_callback: Optional callback(current, total, message)

    Returns True if enrichment succeeded, False otherwise.
    """
    isin = get_isin_from_raw_text(raw_text)
    if not isin:
        logger.debug(f"Product {product_id}: No ISIN found")
        return False

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

    temp_pdf = None
    try:
        # Download PDF from product page
        temp_pdf = download_termsheet_pdf_from_product_page(page, isin)
        if not temp_pdf or not temp_pdf.exists():
            logger.error(f"Product {product_id} ({isin}): PDF download failed")
            return False

        logger.debug(f"Product {product_id} ({isin}): Processing PDF at {temp_pdf}")

        if progress_callback:
            progress_callback(message=f"Parsing PDF for {display_name}")

        # Extract text and parse PDF
        pdf_text = extract_text(temp_pdf)
        parsed_product = parse_pdf(temp_pdf, pdf_text)

        if not parsed_product:
            logger.warning(f"Product {product_id} ({isin}): PDF parsing returned no data")
            return False

        if progress_callback:
            progress_callback(message=f"Merging data for {display_name}")

        # Convert NormalizedProduct to dict
        pdf_data = parsed_product.model_dump()

        # Merge with existing normalized data
        try:
            existing_data = json.loads(normalized_json) if normalized_json else {}
        except json.JSONDecodeError as e:
            logger.error(f"Product {product_id} ({isin}): Cannot parse existing normalized_json, starting fresh: {e}")
            existing_data = {}

        # Update ALL fields from PDF (only if not already present or if PDF has better data)
        updates_made = False

        # List of all possible fields to merge
        fields_to_merge = [
            "isin", "valor_number", "issuer_name", "product_type", "currency",
            "issue_date", "maturity_date", "observation_date", "strike_date",
            "coupon_rate_pct_pa", "barrier_level_pct", "cap_level_pct",
            "participation_rate_pct", "strike_price", "denomination",
            "issue_price", "current_price", "bid_price", "ask_price",
            "underlyings", "payment_dates", "observation_dates",
            "autocall_barrier_pct", "knock_in_barrier_pct", "knock_out_barrier_pct",
            "memory_coupon", "issuer_rating", "guarantee_type",
            "trading_venue", "settlement_type", "exercise_type"
        ]

        for field in fields_to_merge:
            pdf_value = pdf_data.get(field)

            # Skip if PDF doesn't have this field or it's None/empty
            if not pdf_value:
                continue

            # For dict fields (like isin: {value: "CH123", confidence: 0.9})
            if isinstance(pdf_value, dict):
                pdf_actual_value = pdf_value.get("value")
                if not pdf_actual_value:
                    continue

                existing_value = existing_data.get(field, {})
                existing_actual_value = existing_value.get("value") if isinstance(existing_value, dict) else existing_value

                # Update if:
                # 1. Field doesn't exist in existing data
                # 2. Existing value is None/empty
                # 3. PDF has higher confidence
                should_update = (
                    not existing_actual_value or
                    (isinstance(existing_value, dict) and
                     pdf_value.get("confidence", 0) > existing_value.get("confidence", 0))
                )

                if should_update:
                    existing_data[field] = pdf_value
                    updates_made = True
                    logger.debug(f"Product {product_id}: Updated {field} = {pdf_actual_value}")

            # For list fields (like underlyings, payment_dates)
            elif isinstance(pdf_value, list) and pdf_value:
                existing_value = existing_data.get(field, [])
                if not existing_value or len(pdf_value) > len(existing_value):
                    existing_data[field] = pdf_value
                    updates_made = True
                    logger.debug(f"Product {product_id}: Updated {field} with {len(pdf_value)} items")

            # For simple scalar fields
            else:
                if field not in existing_data or not existing_data.get(field):
                    existing_data[field] = pdf_value
                    updates_made = True
                    logger.debug(f"Product {product_id}: Updated {field} = {pdf_value}")

        if updates_made:
            # Update database
            updated_json = json.dumps(existing_data)
            models.update_product_normalized_json(product_id, updated_json)
            logger.info(f"Product {product_id} ({isin}): Enriched successfully with {sum(1 for f in fields_to_merge if f in pdf_data and pdf_data[f])} fields")
            return True
        else:
            logger.debug(f"Product {product_id} ({isin}): No new data to add")
            return False

    except Exception as e:
        logger.error(f"Product {product_id} ({isin}): Enrichment failed: {e}")
        return False
    finally:
        # ALWAYS delete temporary PDF and its directory
        if temp_pdf and temp_pdf.exists():
            temp_pdf.unlink()
            # Also delete temp directory if empty
            if temp_pdf.parent.exists() and not list(temp_pdf.parent.iterdir()):
                temp_pdf.parent.rmdir()
            logger.debug(f"Product {product_id} ({isin}): Deleted temporary PDF")


def enrich_leonteq_products_batch(
    limit: int = 100,
    progress_callback: callable = None,
    checkpoint_file: Path | None = None,
    filter_mode: str = "missing_any"
) -> dict[str, int]:
    """
    Enrich a batch of Leonteq API products by downloading termsheets from product pages.

    Args:
        limit: Maximum number of products to process
        progress_callback: Optional callback(current, total, message, stats)
        checkpoint_file: Optional file to save progress (resume on failure)
        filter_mode: What products to target:
            - "missing_any": Products missing coupons OR barriers (default)
            - "missing_coupon": Only products missing coupon rates
            - "missing_barrier": Only products missing barrier data
            - "all": All Leonteq API products

    Returns:
        Statistics: {"processed": N, "enriched": M, "failed": K, "skipped": S}
    """
    logger.info(f"Starting batch enrichment (limit={limit}, filter={filter_mode})")

    # Load saved state (remembers position between runs)
    saved_state = load_leonteq_state()
    start_offset = saved_state.get("offset", 0)

    if start_offset > 0:
        logger.info(f"Resuming from saved offset: {start_offset} products already processed")

    # Also check legacy checkpoint file if exists
    if checkpoint_file and checkpoint_file.exists():
        try:
            checkpoint_data = json.loads(checkpoint_file.read_text())
            checkpoint_offset = checkpoint_data.get("processed", 0)
            if checkpoint_offset > start_offset:
                start_offset = checkpoint_offset
                logger.info(f"Using checkpoint offset: {start_offset}")
        except Exception as e:
            logger.warning(f"Could not load checkpoint: {e}")

    # Get Leonteq API products based on filter mode
    from backend.app.db.session import get_connection, init_db

    init_db()

    # Build WHERE clause based on filter mode
    if filter_mode == "missing_coupon":
        where_clause = """
            WHERE source_kind = 'leonteq_api'
              AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
        """
    elif filter_mode == "missing_barrier":
        where_clause = """
            WHERE source_kind = 'leonteq_api'
              AND (
                json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
              )
        """
    elif filter_mode == "all":
        where_clause = """
            WHERE source_kind = 'leonteq_api'
        """
    else:  # "missing_any" (default)
        where_clause = """
            WHERE source_kind = 'leonteq_api'
              AND (
                json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
                OR (
                  json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                  AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
                )
              )
        """

    query = f"""
        SELECT id, raw_text, normalized_json
        FROM products
        {where_clause}
        ORDER BY updated_at DESC
        LIMIT ?
    """

    with get_connection() as conn:
        rows = conn.execute(query, (limit + start_offset,)).fetchall()

    all_products = [dict(row) for row in rows]

    # Skip already processed
    products = all_products[start_offset:]
    total = len(products)

    if total == 0:
        logger.info("No products need enrichment")
        return {"processed": 0, "enriched": 0, "failed": 0, "skipped": 0}

    logger.info(f"Found {total} products to process")

    stats = {"processed": start_offset, "enriched": 0, "failed": 0, "skipped": 0}

    # Initialize browser with authentication
    logger.info("Initializing browser for Leonteq...")
    if progress_callback:
        progress_callback(0, total, "Opening browser for Leonteq login...", stats)

    # Get authenticated session (opens visible browser for manual login)
    # This function manages its own browser instance
    logger.info("Please log in to Leonteq in the browser window that will open...")
    if progress_callback:
        progress_callback(0, total, "⚠️ Please log in to Leonteq in the browser window...", stats)

    try:
        storage_state = interactive_login_storage_state()
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return stats

    if not storage_state:
        logger.error("Failed to get Leonteq authentication")
        return stats

    logger.info("Login successful, starting enrichment...")
    if progress_callback:
        progress_callback(0, total, "✓ Logged in successfully, starting enrichment...", stats)

    # Now launch headless browser with saved auth for enrichment
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        try:
            # Create context with stored auth
            context = browser.new_context(storage_state=storage_state)
            page = context.new_page()

            logger.info("Browser initialized and authenticated")

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            browser.close()
            return stats

        try:
            for idx, product in enumerate(products):
                product_id = product["id"]
                raw_text = product.get("raw_text", "")
                normalized_json = product.get("normalized_json", "")
                isin = get_isin_from_raw_text(raw_text) or "unknown"

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

                success = enrich_product_from_pdf(
                    page,
                    product_id,
                    raw_text,
                    normalized_json,
                    progress_callback=lambda message: progress_callback(current, total, message, stats) if progress_callback else None
                )

                if success:
                    stats["enriched"] += 1
                else:
                    stats["failed"] += 1

                # Save state every 5 products (persistent between runs)
                if stats["processed"] % 5 == 0:
                    save_leonteq_state(
                        offset=start_offset + stats["processed"],
                        total_enriched=saved_state.get("total_enriched", 0) + stats["enriched"],
                        total_failed=saved_state.get("total_failed", 0) + stats["failed"]
                    )

                # Save legacy checkpoint every 10 products
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
                time.sleep(1)

        finally:
            page.close()
            context.close()
            browser.close()

    # Save final state
    save_leonteq_state(
        offset=start_offset + stats["processed"],
        total_enriched=saved_state.get("total_enriched", 0) + stats["enriched"],
        total_failed=saved_state.get("total_failed", 0) + stats["failed"]
    )

    # Clear checkpoint on completion
    if checkpoint_file and checkpoint_file.exists():
        checkpoint_file.unlink()
        logger.info("Checkpoint cleared (enrichment complete)")

    logger.info(f"Batch enrichment complete: {stats}")
    logger.info(f"Position saved: will resume from offset {start_offset + stats['processed']} on next run")
    return stats
