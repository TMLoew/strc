from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from backend.app.db import models
from backend.app.settings import settings
from core.sources.leonteq_api import fetch_all_products, fetch_all_products_segmented, parse_api_product
from core.utils.hashing import sha256_text


def crawl_leonteq_api(run_id: str | None = None, api_filters: dict | None = None) -> dict[str, list]:
    """
    Main crawler function for Leonteq API.

    Orchestration flow:
    1. Validate settings (token, enable flag)
    2. Fetch all products via fetch_all_products_segmented()
    3. Apply optional filters (product_types, symbols, currencies)
    4. Update crawl_run.total = len(api_products)
    5. Process each product immediately via callback
    6. Update crawl_run status to "completed" or "failed"
    7. Return {ids: [...], errors: [...]}

    Args:
        run_id: Optional crawl run ID for progress tracking
        api_filters: Optional filters dict with keys:
            - product_types: List of product type codes
            - symbols: List of underlying symbols
            - currencies: List of currency codes

    Returns:
        Dictionary with 'ids' (list of product IDs) and 'errors' (list of error dicts)

    Raises:
        RuntimeError: If Leonteq API crawl is disabled or token not configured
    """
    if not settings.enable_leonteq_api_crawl:
        error_msg = "Leonteq API crawler is disabled in settings"
        if run_id:
            models.update_crawl_run(run_id, status="failed", last_error=error_msg)
        raise RuntimeError("leonteq_api_crawl_disabled")

    if not settings.leonteq_api_token:
        error_msg = "API token not configured. Click 'Open Leonteq login' to capture token automatically."
        if run_id:
            models.update_crawl_run(run_id, status="failed", last_error=error_msg)
        raise ValueError(error_msg)

    ids: list[str] = []
    errors: list[dict[str, str]] = []
    lock = Lock()
    total_set = False

    try:
        # Log filter info
        filter_info = ""
        if api_filters:
            filter_parts = []
            if api_filters.get("product_types"):
                filter_parts.append(f"product_types={api_filters['product_types']}")
            if api_filters.get("symbols"):
                filter_parts.append(f"symbols={api_filters['symbols']}")
            if api_filters.get("currencies"):
                filter_parts.append(f"currencies={api_filters['currencies']}")
            filter_info = f" with filters: {', '.join(filter_parts)}" if filter_parts else ""

        # Use segmented crawl to bypass 10K limit
        print(f"Leonteq API crawl: Starting segmented crawl{filter_info} (page_size={settings.leonteq_api_page_size}, max_products={settings.leonteq_api_max_products})")

        def progress_callback(completed: int, total: int):
            """Progress callback - updates during fetch."""
            nonlocal total_set
            if run_id:
                if not total_set and total > 0:
                    models.update_crawl_run(run_id, total=total)
                    print(f"Leonteq API crawl: Found {total} products")
                    total_set = True

        def product_callback(api_product_dict: dict):
            """Process each product immediately after fetch."""
            try:
                # Parse API product to NormalizedProduct
                product = parse_api_product(api_product_dict)

                # Extract ISIN for deduplication hash
                isin = product.isin.value
                if not isin:
                    raise ValueError("Parsed product missing ISIN")

                # Store product in database immediately
                product_id = models.upsert_product(
                    normalized=product.model_dump(),
                    raw_text=json.dumps(api_product_dict, indent=2),
                    source_kind="leonteq_api",
                    source_file_path=None,
                    source_file_hash_sha256=sha256_text(f"leonteq_api:{isin}")
                )

                with lock:
                    ids.append(product_id)

                # Increment progress
                if run_id:
                    models.increment_crawl_completed(run_id)

            except Exception as exc:
                # Extract identifiers for error reporting
                isin = api_product_dict.get("identifiers", {}).get("isin", "unknown")
                valor = api_product_dict.get("identifiers", {}).get("valor", "unknown")

                with lock:
                    errors.append({
                        "isin": isin,
                        "valor": str(valor),
                        "source": "leonteq_api",
                        "error": str(exc)
                    })

                if run_id:
                    models.increment_crawl_errors(run_id, f"leonteq_api:{isin}:{exc}")

        # Fetch with segmented approach (bypasses 10K limit)
        fetch_all_products_segmented(
            token=settings.leonteq_api_token,
            page_size=settings.leonteq_api_page_size,
            max_products=settings.leonteq_api_max_products,
            progress_callback=progress_callback,
            product_callback=product_callback,  # Process immediately!
            checkpoint_callback=None,  # Segmented mode doesn't use checkpoints
            rate_limit_ms=settings.leonteq_api_rate_limit_ms,
            user_filters=api_filters,  # Apply user-specified filters
        )

        print(f"Leonteq API crawl: Processed {len(ids)} products successfully, {len(errors)} errors")

        # Mark crawl as completed
        if run_id:
            models.update_crawl_run(run_id, status="completed")

        print(f"Leonteq API crawl completed: {len(ids)} products stored, {len(errors)} errors")

    except Exception as exc:
        # Mark crawl as failed
        if run_id:
            models.update_crawl_run(run_id, status="failed", last_error=str(exc))
        print(f"Leonteq API crawl failed: {exc}")
        raise

    return {"ids": ids, "errors": errors}
