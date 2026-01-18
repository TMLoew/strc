"""API endpoints for data enrichment from various sources."""

import asyncio
import logging
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from fastapi import APIRouter, HTTPException

from backend.app.services.leonteq_pdf_enrichment import (
    enrich_leonteq_products_batch,
    load_leonteq_state,
    reset_leonteq_state,
)
from backend.app.services.finanzen_crawler_service import enrich_products_from_finanzen_batch
from backend.app.services.auto_enrichment import (
    AutoEnrichmentState,
    run_auto_enrichment_cycle,
    get_total_missing_coupons,
)

router = APIRouter(prefix="/enrich", tags=["enrich"])
logger = logging.getLogger(__name__)

# Thread pool for running sync Playwright code (enrichment tasks)
executor = ThreadPoolExecutor(max_workers=4)

# Separate pool for quick DB queries (avoid deadlock)
db_executor = ThreadPoolExecutor(max_workers=2)

# Auto-enrichment state (global)
auto_enrich_state = AutoEnrichmentState().load()
auto_enrich_running = False
auto_enrich_task = None


@router.post("/leonteq-pdfs")
async def enrich_leonteq_pdfs(
    limit: int = 100,
    filter_mode: str = "missing_any"
) -> dict[str, Any]:
    """
    Enrich Leonteq API products by extracting data from termsheet PDFs.

    PDFs are downloaded temporarily and deleted after processing.
    Only extracted structured data is saved to the database.

    Args:
        limit: Maximum number of products to process (default: 100)
        filter_mode: What products to target (default: "missing_any"):
            - "missing_coupon": Only products missing coupon rates
            - "missing_barrier": Only products missing barrier data
            - "missing_any": Products missing coupons OR barriers (RECOMMENDED)
            - "all": All Leonteq API products

    Returns:
        Statistics: {"processed": N, "enriched": M, "failed": K}
    """
    try:
        # Run sync Playwright code in separate thread to avoid event loop conflict
        loop = asyncio.get_event_loop()
        func = partial(enrich_leonteq_products_batch, limit=limit, filter_mode=filter_mode)
        stats = await loop.run_in_executor(executor, func)
        return stats
    except Exception as e:
        logger.error(f"Leonteq PDF enrichment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


@router.post("/finanzen-ch")
async def enrich_from_finanzen(
    limit: int = 100,
    filter_mode: str = "missing_coupon"
) -> dict[str, Any]:
    """
    Enrich products by scraping data from finanzen.ch.

    Uses browser automation to fetch product pages and extract:
    - Coupon rates (CRITICAL for barrier reverse convertibles)
    - Barrier levels
    - Strike prices
    - Cap levels
    - Participation rates
    - Maturity dates

    Args:
        limit: Maximum number of products to process (default: 100)
        filter_mode: What products to target (default: "missing_coupon"):
            - "missing_coupon": Only products missing coupon rates (RECOMMENDED)
            - "missing_barrier": Only products missing barrier data
            - "missing_any": Products missing coupons OR barriers
            - "all_with_isin": All products that have ISINs

    Returns:
        Statistics: {"processed": N, "enriched": M, "failed": K}
    """
    try:
        # Run sync Playwright code in separate thread to avoid event loop conflict
        loop = asyncio.get_event_loop()
        func = partial(enrich_products_from_finanzen_batch, limit=limit, filter_mode=filter_mode)
        stats = await loop.run_in_executor(executor, func)
        return stats
    except Exception as e:
        logger.error(f"Finanzen.ch enrichment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


@router.post("/auto/start")
async def start_auto_enrichment(batch_size: int = 10) -> dict[str, Any]:
    """
    Start continuous auto-enrichment in the background.

    Progressively enriches products with missing data, remembering position
    between runs for seamless resumption.

    Args:
        batch_size: Number of products to process per cycle (default: 10)

    Returns:
        Status information
    """
    global auto_enrich_running, auto_enrich_task, auto_enrich_state

    if auto_enrich_running:
        raise HTTPException(status_code=400, detail="Auto-enrichment is already running")

    auto_enrich_running = True
    auto_enrich_state.load()  # Reload state

    logger.info(f"Starting auto-enrichment (batch_size={batch_size})")

    # Start background task
    async def run_cycles():
        global auto_enrich_running
        logger.info("Auto-enrichment background task started")
        while auto_enrich_running:
            try:
                logger.debug(f"Starting auto-enrich cycle (batch={batch_size})")
                # Run one cycle in executor
                loop = asyncio.get_event_loop()
                func = partial(
                    run_auto_enrichment_cycle,
                    state=auto_enrich_state,
                    batch_size=batch_size
                )
                await loop.run_in_executor(executor, func)
                logger.debug("Auto-enrich cycle completed")

                # Wait between cycles
                await asyncio.sleep(30)  # 30 seconds between cycles

            except Exception as e:
                logger.error(f"Auto-enrichment cycle error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on error

        logger.info("Auto-enrichment background task stopped")

    auto_enrich_task = asyncio.create_task(run_cycles())

    # Give the task a moment to start
    await asyncio.sleep(0.1)

    return {
        "status": "started",
        "batch_size": batch_size,
        "current_offset": auto_enrich_state.finanzen_offset,
        "total_enriched": auto_enrich_state.total_enriched,
        "total_failed": auto_enrich_state.total_failed,
    }


@router.post("/auto/stop")
async def stop_auto_enrichment() -> dict[str, Any]:
    """Stop auto-enrichment."""
    global auto_enrich_running, auto_enrich_task

    if not auto_enrich_running:
        raise HTTPException(status_code=400, detail="Auto-enrichment is not running")

    logger.info("Stopping auto-enrichment")
    auto_enrich_running = False

    # Wait for task to complete
    if auto_enrich_task:
        try:
            await asyncio.wait_for(auto_enrich_task, timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Auto-enrichment task did not stop cleanly")
            auto_enrich_task.cancel()

    return {
        "status": "stopped",
        "total_enriched": auto_enrich_state.total_enriched,
        "total_failed": auto_enrich_state.total_failed,
    }


@router.get("/auto/status")
async def get_auto_enrichment_status() -> dict[str, Any]:
    """Get current auto-enrichment status."""
    global auto_enrich_state

    # Reload state to get latest
    auto_enrich_state.load()

    # Get total missing in separate DB executor to avoid blocking
    loop = asyncio.get_event_loop()
    total_missing = await loop.run_in_executor(db_executor, get_total_missing_coupons)

    progress_pct = 0
    if total_missing > 0:
        # Calculate rough progress (offset / total)
        total_products = total_missing + auto_enrich_state.finanzen_offset
        if total_products > 0:
            progress_pct = min(100, int((auto_enrich_state.finanzen_offset / total_products) * 100))

    return {
        "running": auto_enrich_running,
        "finanzen_offset": auto_enrich_state.finanzen_offset,
        "total_enriched": auto_enrich_state.total_enriched,
        "total_failed": auto_enrich_state.total_failed,
        "total_missing": total_missing,
        "progress_pct": progress_pct,
        "last_run": auto_enrich_state.last_run,
    }


@router.post("/auto/reset")
async def reset_auto_enrichment() -> dict[str, Any]:
    """Reset auto-enrichment position to start from beginning."""
    global auto_enrich_state

    if auto_enrich_running:
        raise HTTPException(
            status_code=400,
            detail="Cannot reset while auto-enrichment is running. Stop it first."
        )

    auto_enrich_state.reset()

    return {
        "status": "reset",
        "message": "Auto-enrichment will start from the beginning on next run",
    }


@router.get("/leonteq/status")
async def get_leonteq_status() -> dict[str, Any]:
    """Get Leonteq PDF enrichment status (saved position)."""
    loop = asyncio.get_event_loop()
    state = await loop.run_in_executor(db_executor, load_leonteq_state)

    return {
        "offset": state.get("offset", 0),
        "total_enriched": state.get("total_enriched", 0),
        "total_failed": state.get("total_failed", 0),
        "last_run": state.get("last_run"),
    }


@router.post("/leonteq/reset")
async def reset_leonteq_position() -> dict[str, Any]:
    """Reset Leonteq PDF enrichment position to start from beginning."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(db_executor, reset_leonteq_state)

    return {
        "status": "reset",
        "message": "Leonteq enrichment will start from the beginning on next run",
    }
