import json
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.db import models
from backend.app.settings import settings
from backend.app.services import (
    best_risk_reward,
    derived_metrics,
    ingest_finanzen_isin,
    ingest_swissquote_isin,
    ingest_yahoo_isin,
)
from backend.app.services.leonteq_service import ingest_leonteq_isin

router = APIRouter(prefix="/products", tags=["products"])


class ReviewRequest(BaseModel):
    status: str


class ISINRequest(BaseModel):
    isin: str


class SearchRequest(BaseModel):
    query: str


ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
PDF_RE = re.compile(r"https?://[^\s\"']+?\.pdf[^\s\"']*")
FACTSHEET_EN_RE = re.compile(r"https?://api\.factsheet-hub\.ch/[^\s\"']+\bl=en")


def _extract_english_termsheet(raw_text: str | None) -> str | None:
    if not raw_text:
        return None
    match = FACTSHEET_EN_RE.search(raw_text)
    if match:
        return match.group(0)
    match = PDF_RE.search(raw_text)
    return match.group(0) if match else None


@router.get("")
def list_products(
    limit: int = 200,
    offset: int = 0,
    source: str | None = None,
    product_type: str | None = None
) -> dict[str, Any]:
    """
    List products with optional filtering.

    Args:
        limit: Maximum number of products to return
        offset: Number of products to skip
        source: Filter by data source (e.g., 'akb_finanzportal', 'leonteq_api', 'swissquote')
        product_type: Filter by product type (e.g., 'Express-Zertifikat', 'Barrier Reverse Convertible')

    Returns:
        Dict with items, total, limit, offset, and applied filters
    """
    records = models.list_products(
        limit=limit,
        offset=offset,
        source_kind=source,
        product_type=product_type
    )

    total = models.count_products(source_kind=source, product_type=product_type)

    for record in records:
        if record.get("normalized_json"):
            record["normalized_json"] = json.loads(record["normalized_json"])
        record["english_termsheet_url"] = _extract_english_termsheet(record.get("raw_text"))
        record.pop("raw_text", None)

    response = {
        "items": records,
        "total": total,
        "limit": limit,
        "offset": offset
    }

    if source or product_type:
        response["filters"] = {
            "source": source,
            "product_type": product_type
        }

    return response


@router.get("/filters/sources")
def get_available_sources() -> dict[str, list[dict[str, Any]]]:
    """Get available data sources for filtering."""
    from backend.app.db.session import get_connection, init_db

    init_db()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT source_kind, COUNT(*) as count
            FROM products
            GROUP BY source_kind
            ORDER BY count DESC
        """).fetchall()

    sources = [
        {
            "value": row["source_kind"],
            "label": row["source_kind"].replace("_", " ").title(),
            "count": row["count"]
        }
        for row in rows
    ]

    return {"sources": sources}


@router.get("/filters/product-types")
def get_available_product_types(source: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """
    Get available product types for filtering.

    Args:
        source: Optional source filter to get product types only from that source
    """
    from backend.app.db.session import get_connection, init_db

    init_db()

    query = """
        SELECT product_type, COUNT(*) as count
        FROM products
        WHERE product_type IS NOT NULL
    """
    params: list[Any] = []

    if source:
        query += " AND source_kind = ?"
        params.append(source)

    query += " GROUP BY product_type ORDER BY count DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    product_types = [
        {
            "value": row["product_type"],
            "label": row["product_type"],
            "count": row["count"]
        }
        for row in rows
    ]

    return {"product_types": product_types}


@router.get("/best")
def list_best(limit: int = 10) -> dict[str, Any]:
    return {"products": best_risk_reward(limit)}


@router.get("/{product_id}")
def get_product(product_id: str) -> dict[str, Any]:
    record = models.get_product(product_id)
    if not record:
        raise HTTPException(status_code=404, detail="Product not found")
    record["normalized_json"] = json.loads(record["normalized_json"])
    record["derived"] = derived_metrics(record["normalized_json"])
    return record


@router.post("/{product_id}/review")
def update_review(product_id: str, payload: ReviewRequest) -> dict[str, str]:
    record = models.get_product(product_id)
    if not record:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.status in {"reviewed", "to_be_signed"} and record.get("source_file_path"):
        source_path = Path(record["source_file_path"])
        target_dir = settings.reviewed_dir if payload.status == "reviewed" else settings.to_be_signed_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        if source_path.exists():
            dest = target_dir / source_path.name
            if dest.exists():
                dest = target_dir / f"{product_id}-{source_path.name}"
            shutil.move(str(source_path), dest)
            models.update_source_file_path(product_id, str(dest))

    models.update_review_status(product_id, payload.status)
    return {"status": payload.status}


@router.post("/clear")
def clear_all_products() -> dict[str, str]:
    models.clear_products()
    return {"status": "cleared"}


@router.post("/clear-incomplete")
def clear_incomplete_products() -> dict[str, Any]:
    """
    Delete products missing critical fields based on their type.

    Removes:
    - Barrier products without barrier data
    - Coupon products without coupon data
    - Products without underlyings (when expected)
    """
    from backend.app.db.session import get_connection

    deleted_count = 0

    with get_connection() as conn:
        # Delete barrier products without barrier data
        result = conn.execute("""
            DELETE FROM products
            WHERE (
                product_type LIKE '%Barrier%'
                OR product_type LIKE '%barrier%'
            )
            AND (
                json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
            )
        """)
        deleted_count += result.rowcount

        # Delete reverse convertibles / express certificates without coupons
        result = conn.execute("""
            DELETE FROM products
            WHERE (
                product_type LIKE '%Reverse Convertible%'
                OR product_type LIKE '%Express%'
                OR product_type LIKE '%Credit Linked%'
            )
            AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
        """)
        deleted_count += result.rowcount

        # Delete structured products without underlyings
        result = conn.execute("""
            DELETE FROM products
            WHERE (
                product_type NOT LIKE '%Bond%'
                AND product_type NOT LIKE '%Anleihe%'
                AND product_type NOT LIKE '%Obligation%'
            )
            AND (
                json_extract(normalized_json, '$.underlyings') IS NULL
                OR json_type(json_extract(normalized_json, '$.underlyings')) != 'array'
                OR json_array_length(json_extract(normalized_json, '$.underlyings')) = 0
            )
        """)
        deleted_count += result.rowcount

        conn.commit()

    return {"deleted": deleted_count, "status": "cleaned"}


@router.post("/leonteq/by-isin")
def add_by_isin(payload: ISINRequest) -> dict[str, str]:
    product_id = ingest_leonteq_isin(payload.isin)
    return {"id": product_id}


@router.get("/search/isin/{isin}")
def search_by_isin(isin: str) -> dict[str, Any]:
    """
    Search for products by ISIN in the database.

    Args:
        isin: ISIN code to search for (case-insensitive)

    Returns:
        List of matching products with full details
    """
    from backend.app.db.session import get_connection, init_db

    init_db()
    isin_upper = isin.strip().upper()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM products
            WHERE UPPER(isin) = ?
            ORDER BY updated_at DESC
            LIMIT 10
        """, (isin_upper,)).fetchall()

    products = []
    for row in rows:
        record = dict(row)
        if record.get("normalized_json"):
            record["normalized_json"] = json.loads(record["normalized_json"])
        record["english_termsheet_url"] = _extract_english_termsheet(record.get("raw_text"))
        record.pop("raw_text", None)
        products.append(record)

    return {
        "isin": isin_upper,
        "count": len(products),
        "products": products
    }


@router.post("/search")
def search_products(payload: SearchRequest) -> dict[str, list[str]]:
    query = payload.query.strip().upper()

    # Try to detect what kind of search this is
    # ISIN: 2 letters followed by 10 alphanumeric characters
    # Valor: 6-9 digits
    # Symbol: anything else (try as symbol)

    ids: list[str] = []
    errors: list[dict[str, str]] = []

    is_isin = ISIN_RE.match(query)
    is_valor = query.isdigit() and 6 <= len(query) <= 9

    if is_isin:
        # ISIN search - fetch from external sources
        try:
            ids.append(ingest_leonteq_isin(query))
        except Exception as exc:
            errors.append({"source": "leonteq", "error": str(exc)})
            try:
                ids.append(ingest_finanzen_isin(query))
            except Exception as fin_exc:
                errors.append({"source": "finanzen", "error": str(fin_exc)})
        sq_id = ingest_swissquote_isin(query)
        if sq_id:
            ids.append(sq_id)
        if settings.enable_yahoo_enrich:
            try:
                yahoo_id = ingest_yahoo_isin(query)
                if yahoo_id:
                    ids.append(yahoo_id)
            except Exception as exc:
                errors.append({"source": "yahoo", "error": str(exc)})
    elif is_valor:
        # Valor search - look in database first, then try external sources
        from backend.app.db.session import get_connection, init_db
        init_db()
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT id FROM products
                WHERE valor_number = ?
                LIMIT 5
            """, (query,)).fetchall()
            ids.extend([row["id"] for row in rows])

        if not ids:
            errors.append({"source": "database", "error": f"No products found with Valor {query}"})
    else:
        # Symbol/ticker search - look in database
        from backend.app.db.session import get_connection, init_db
        init_db()
        with get_connection() as conn:
            # Search in normalized_json for symbol/ticker
            rows = conn.execute("""
                SELECT id FROM products
                WHERE json_extract(normalized_json, '$.symbol.value') = ?
                   OR json_extract(normalized_json, '$.ticker.value') = ?
                LIMIT 5
            """, (query, query)).fetchall()
            ids.extend([row["id"] for row in rows])

        if not ids:
            errors.append({"source": "database", "error": f"No products found with symbol '{query}'"})

    return {"ids": ids, "errors": errors}
