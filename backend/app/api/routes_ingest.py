from fastapi import APIRouter

from fastapi import BackgroundTasks

from backend.app.db import models
from backend.app.settings import settings
from backend.app.services import (
    crawl_akb_catalog,
    crawl_akb_enrich,
    crawl_akb_portal_catalog,
    crawl_swissquote_scanner,
    ingest_directory,
    pop_swissquote_creds,
    store_swissquote_creds,
    store_session_state,
    clear_session_state,
)
from backend.app.services.leonteq_api_crawler_service import crawl_leonteq_api
from pydantic import BaseModel
from core.sources.swissquote_scanner import interactive_login_storage_state
from core.sources.leonteq import interactive_login_storage_state as leonteq_interactive_login
from backend.app.services.leonteq_session_service import (
    store_leonteq_session_state,
    clear_leonteq_session_state,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/run")
def run_ingest() -> dict[str, list[str]]:
    ids = ingest_directory()
    return {"ids": ids}


@router.post("/crawl/akb")
def crawl_akb(background_tasks: BackgroundTasks) -> dict:
    """
    Start AKB catalog crawler as background task.

    Returns:
        dict: {"run_id": "uuid-string"}

    Usage:
        1. Call this endpoint to start the crawl
        2. Poll GET /ingest/crawl/status/{run_id} to check progress
    """
    run_id = models.create_crawl_run("akb_catalog")
    print(f"AKB catalog crawl started: {run_id}")
    background_tasks.add_task(crawl_akb_catalog, run_id)
    return {"run_id": run_id}


@router.post("/crawl/akb-enrich")
def crawl_akb_with_enrich(background_tasks: BackgroundTasks) -> dict:
    """
    Start AKB enrichment crawler as background task.

    Fetches ISINs from AKB catalog and enriches with data from:
    - Leonteq (HTML + PDF)
    - Swissquote
    - Yahoo Finance (if enabled)

    Returns:
        dict: {"run_id": "uuid-string"}

    Usage:
        1. Call this endpoint to start the crawl
        2. Poll GET /ingest/crawl/status/{run_id} to check progress
    """
    run_id = models.create_crawl_run("akb_enrich")
    print(f"AKB enrich crawl started: {run_id}")
    background_tasks.add_task(crawl_akb_enrich, run_id)
    return {"run_id": run_id}


@router.post("/crawl/akb-portal")
def crawl_akb_portal(background_tasks: BackgroundTasks) -> dict:
    run_id = models.create_crawl_run("akb_portal")
    print(f"AKB portal crawl started: {run_id}")
    background_tasks.add_task(crawl_akb_portal_catalog, run_id)
    return {"run_id": run_id}


@router.post("/crawl/swissquote-scanner")
def crawl_swissquote_scanner_endpoint(background_tasks: BackgroundTasks) -> dict:
    run_id = models.create_crawl_run("swissquote_scanner")
    print(f"Swissquote scanner crawl started: {run_id}")
    background_tasks.add_task(crawl_swissquote_scanner, run_id)
    return {"run_id": run_id}


class SwissquoteAuthRequest(BaseModel):
    username: str
    password: str


@router.post("/crawl/swissquote-scanner-auth")
def crawl_swissquote_scanner_auth(
    payload: SwissquoteAuthRequest, background_tasks: BackgroundTasks
) -> dict:
    token = store_swissquote_creds(payload.username, payload.password)
    run_id = models.create_crawl_run("swissquote_scanner")

    def run_with_creds() -> None:
        creds = pop_swissquote_creds(token)
        if not creds:
            models.update_crawl_run(run_id, status="failed", last_error="missing_credentials")
            return
        crawl_swissquote_scanner(run_id, username=creds.username, password=creds.password)

    print(f"Swissquote scanner crawl started: {run_id}")
    background_tasks.add_task(run_with_creds)
    return {"run_id": run_id}


@router.post("/swissquote/login")
def swissquote_login() -> dict:
    state = interactive_login_storage_state()
    store_session_state(state)
    return {"status": "ok"}


@router.post("/swissquote/logout")
def swissquote_logout() -> dict:
    clear_session_state()
    return {"status": "cleared"}


@router.post("/leonteq/login")
def leonteq_login() -> dict:
    state = leonteq_interactive_login()
    store_leonteq_session_state(state)
    return {"status": "ok"}


@router.post("/leonteq/logout")
def leonteq_logout() -> dict:
    clear_leonteq_session_state()
    return {"status": "cleared"}


class LeonteqCrawlFilters(BaseModel):
    """Filters for Leonteq API crawl."""
    product_types: list[str] | None = None  # e.g., ["PT_BARRIER_REVERSE_CONVERTIBLE", "PT_AUTOCALLABLE"]
    symbols: list[str] | None = None  # e.g., ["AAPL", "GOOGL"]
    currencies: list[str] | None = None  # e.g., ["CHF", "USD"]


@router.post("/crawl/leonteq-api")
def crawl_leonteq_api_endpoint(
    background_tasks: BackgroundTasks,
    filters: LeonteqCrawlFilters | None = None
) -> dict:
    """
    Start Leonteq API crawler as background task.

    Args:
        filters: Optional filters to limit what products are fetched:
            - product_types: List of product type codes (e.g., ["PT_WARRANT", "PT_BARRIER_REVERSE_CONVERTIBLE"])
            - symbols: List of underlying symbols to search for (e.g., ["AAPL", "GOOGL"])
            - currencies: List of currencies to filter by (e.g., ["CHF", "USD"])

    Returns:
        dict: {"run_id": "uuid-string"}

    Usage:
        1. Call this endpoint to start the crawl
        2. Poll GET /ingest/crawl/status/{run_id} to check progress

    Examples:
        # Fetch all products:
        POST /api/ingest/crawl/leonteq-api

        # Fetch only barrier reverse convertibles:
        POST /api/ingest/crawl/leonteq-api
        {"product_types": ["PT_BARRIER_REVERSE_CONVERTIBLE"]}

        # Fetch products on Apple or Google:
        POST /api/ingest/crawl/leonteq-api
        {"symbols": ["AAPL", "GOOGL"]}
    """
    run_id = models.create_crawl_run("leonteq_api")
    print(f"Leonteq API crawl started: {run_id}")

    # Convert filters to dict for crawler
    filter_dict = None
    if filters:
        filter_dict = filters.model_dump(exclude_none=True)

    background_tasks.add_task(crawl_leonteq_api, run_id, filter_dict)
    return {"run_id": run_id}


@router.get("/leonteq-api/product-types")
def get_leonteq_product_types() -> dict:
    """
    Get available product types from existing Leonteq data.

    Returns a list of product type codes that can be used for filtering.

    Returns:
        dict: {"product_types": [{"code": "PT_WARRANT", "count": 1234, "name": "Warrant"}, ...]}
    """
    from backend.app.db.session import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT
        json_extract(raw_text, '$.identification.productType') as product_type,
        json_extract(raw_text, '$.identification.productTypeI18N.en') as product_name,
        COUNT(*) as count
    FROM products
    WHERE source_kind = 'leonteq_api'
        AND product_type IS NOT NULL
    GROUP BY product_type
    ORDER BY count DESC
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    product_types = [
        {
            "code": row[0],
            "name": row[1] or row[0],
            "count": row[2]
        }
        for row in rows
    ]

    return {"product_types": product_types}


@router.post("/crawl/leonteq-api/resume/{run_id}")
def resume_leonteq_api_crawl(run_id: str, background_tasks: BackgroundTasks) -> dict:
    """
    Resume a failed Leonteq API crawl from its last checkpoint.

    Args:
        run_id: The ID of the failed crawl run to resume

    Returns:
        dict: {"status": "ok", "message": "..."}

    Usage:
        POST /ingest/crawl/leonteq-api/resume/{run_id}
    """
    run = models.get_crawl_run(run_id)
    if not run:
        return {"status": "error", "message": "Crawl run not found"}

    if run["status"] not in ["failed", "paused"]:
        return {"status": "error", "message": f"Cannot resume crawl with status: {run['status']}"}

    checkpoint_offset = run.get("checkpoint_offset", 0)
    if checkpoint_offset == 0:
        return {"status": "error", "message": "No checkpoint found to resume from"}

    # Reset status to running
    models.update_crawl_run(run_id, status="running", last_error=None)

    print(f"Leonteq API crawl resuming from checkpoint {checkpoint_offset}: {run_id}")
    background_tasks.add_task(crawl_leonteq_api, run_id)

    return {
        "status": "ok",
        "message": f"Resuming crawl from offset {checkpoint_offset}",
        "checkpoint_offset": checkpoint_offset
    }


@router.get("/crawl/status/{run_id}")
def crawl_status(run_id: str) -> dict:
    run = models.get_crawl_run(run_id)
    if not run:
        return {"error": "not_found"}
    return run


@router.get("/duplicates/stats")
def get_duplicate_stats() -> dict:
    """
    Get statistics about duplicate ISINs across sources.

    Identifies both intentional duplicates (cross-source) and suspicious duplicates
    (same source, same ISIN, same maturity date).
    """
    import sqlite3

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row

    # Get cross-source duplicates (expected/good)
    cross_source_query = """
    SELECT isin, COUNT(*) as total_count, GROUP_CONCAT(source_kind) as sources
    FROM products
    WHERE isin IS NOT NULL
    GROUP BY isin
    HAVING COUNT(*) > 1
    ORDER BY total_count DESC
    LIMIT 100
    """

    cross_source_duplicates = [dict(row) for row in conn.execute(cross_source_query).fetchall()]

    # Get same-source duplicates (suspicious)
    same_source_query = """
    SELECT isin, source_kind, maturity_date, COUNT(*) as count,
           GROUP_CONCAT(id) as product_ids
    FROM products
    WHERE isin IS NOT NULL
    GROUP BY isin, source_kind, maturity_date
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 50
    """

    same_source_duplicates = [dict(row) for row in conn.execute(same_source_query).fetchall()]

    # Get summary stats
    cross_source_stats_query = """
    SELECT
        COUNT(DISTINCT isin) as unique_isins_with_duplicates,
        SUM(count - 1) as total_duplicate_records
    FROM (
        SELECT isin, COUNT(*) as count
        FROM products
        WHERE isin IS NOT NULL
        GROUP BY isin
        HAVING COUNT(*) > 1
    )
    """

    same_source_stats_query = """
    SELECT COUNT(*) as suspicious_duplicate_groups,
           SUM(count - 1) as total_suspicious_duplicates
    FROM (
        SELECT isin, source_kind, maturity_date, COUNT(*) as count
        FROM products
        WHERE isin IS NOT NULL
        GROUP BY isin, source_kind, maturity_date
        HAVING COUNT(*) > 1
    )
    """

    cross_source_stats = dict(conn.execute(cross_source_stats_query).fetchone()) or {}
    same_source_stats = dict(conn.execute(same_source_stats_query).fetchone()) or {}

    conn.close()

    return {
        "cross_source_duplicates": {
            "stats": cross_source_stats,
            "sample": cross_source_duplicates[:20],
            "note": "These are intentional - same ISIN from different sources (AKB, Leonteq, Swissquote). The /products/best endpoint merges them."
        },
        "suspicious_duplicates": {
            "stats": same_source_stats,
            "sample": same_source_duplicates,
            "note": "Same ISIN + same source + same maturity date. These should not exist due to UNIQUE constraint on source_file_hash_sha256."
        }
    }


@router.get("/status/dashboard")
def status_dashboard() -> dict:
    """
    Get comprehensive status for dashboard.

    Returns current status of all recent crawls and database statistics.
    """
    import sqlite3
    from datetime import datetime, timedelta

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get recent crawls (last 10)
    cursor.execute("""
        SELECT * FROM crawl_runs
        ORDER BY started_at DESC
        LIMIT 10
    """)
    recent_crawls = [dict(row) for row in cursor.fetchall()]

    # Get active crawls (running or recently completed)
    cursor.execute("""
        SELECT * FROM crawl_runs
        WHERE status = 'running'
        OR (status IN ('completed', 'failed') AND updated_at > datetime('now', '-1 hour'))
        ORDER BY started_at DESC
    """)
    active_crawls = [dict(row) for row in cursor.fetchall()]

    # Get product counts by source
    cursor.execute("""
        SELECT source_kind, COUNT(*) as count
        FROM products
        GROUP BY source_kind
        ORDER BY count DESC
    """)
    products_by_source = [{"source": row["source_kind"], "count": row["count"]} for row in cursor.fetchall()]

    # Get total product count
    cursor.execute("SELECT COUNT(*) as total FROM products")
    total_products = cursor.fetchone()["total"]

    # Get recent imports (last 24 hours)
    cursor.execute("""
        SELECT COUNT(*) as count FROM products
        WHERE created_at > datetime('now', '-24 hours')
    """)
    recent_imports = cursor.fetchone()["count"]

    # Get error count for active crawls
    cursor.execute("""
        SELECT SUM(errors_count) as total_errors FROM crawl_runs
        WHERE status = 'running'
    """)
    result = cursor.fetchone()
    active_errors = result["total_errors"] if result and result["total_errors"] else 0

    conn.close()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "active_crawls": active_crawls,
        "recent_crawls": recent_crawls,
        "statistics": {
            "total_products": total_products,
            "recent_imports_24h": recent_imports,
            "active_errors": active_errors,
            "products_by_source": products_by_source
        }
    }


@router.post("/crawl/{run_id}/pause")
def pause_crawl(run_id: str) -> dict:
    """Pause a running crawl."""
    run = models.get_crawl_run(run_id)
    if not run:
        return {"status": "error", "message": "Crawl run not found"}
    if run["status"] != "running":
        return {"status": "error", "message": f"Cannot pause crawl with status: {run['status']}"}

    models.pause_crawl_run(run_id)
    return {"status": "ok", "message": "Crawl paused"}


@router.post("/crawl/{run_id}/resume")
def resume_crawl(run_id: str) -> dict:
    """Resume a paused crawl."""
    run = models.get_crawl_run(run_id)
    if not run:
        return {"status": "error", "message": "Crawl run not found"}
    if run["status"] != "paused":
        return {"status": "error", "message": f"Cannot resume crawl with status: {run['status']}"}

    models.resume_crawl_run(run_id)
    return {"status": "ok", "message": "Crawl resumed"}


@router.post("/crawl/{run_id}/cancel")
def cancel_crawl(run_id: str) -> dict:
    """Cancel a running or paused crawl."""
    run = models.get_crawl_run(run_id)
    if not run:
        return {"status": "error", "message": "Crawl run not found"}
    if run["status"] not in ["running", "paused"]:
        return {"status": "error", "message": f"Cannot cancel crawl with status: {run['status']}"}

    models.cancel_crawl_run(run_id)
    return {"status": "ok", "message": "Crawl cancelled"}
