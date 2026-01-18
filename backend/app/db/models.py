from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.db.session import get_connection, init_db
from core.utils.yield_metrics import apply_yield_fields


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_product(
    normalized: dict[str, Any],
    raw_text: str | None,
    source_kind: str,
    source_file_path: str | None,
    source_file_hash_sha256: str | None,
) -> str:
    init_db()
    product_id = normalized.get("id") or str(uuid4())
    normalized["id"] = product_id
    apply_yield_fields(normalized)
    isin = normalized.get("isin", {}).get("value") if isinstance(normalized.get("isin"), dict) else None
    valor = normalized.get("valor_number", {}).get("value") if isinstance(normalized.get("valor_number"), dict) else None
    issuer = normalized.get("issuer_name", {}).get("value") if isinstance(normalized.get("issuer_name"), dict) else None
    product_type = normalized.get("product_type", {}).get("value") if isinstance(normalized.get("product_type"), dict) else None
    currency = normalized.get("currency", {}).get("value") if isinstance(normalized.get("currency"), dict) else None
    maturity = normalized.get("maturity_date", {}).get("value") if isinstance(normalized.get("maturity_date"), dict) else None

    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO products (
                id, isin, valor_number, issuer_name, product_type, currency, maturity_date,
                review_status, source_kind, normalized_json, raw_text, source_file_path,
                source_file_hash_sha256, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_file_hash_sha256) DO UPDATE SET
                isin = excluded.isin,
                valor_number = excluded.valor_number,
                issuer_name = excluded.issuer_name,
                product_type = excluded.product_type,
                currency = excluded.currency,
                maturity_date = excluded.maturity_date,
                source_kind = excluded.source_kind,
                normalized_json = excluded.normalized_json,
                raw_text = excluded.raw_text,
                source_file_path = excluded.source_file_path,
                updated_at = excluded.updated_at
            """,
            (
                product_id,
                isin,
                valor,
                issuer,
                product_type,
                currency,
                maturity,
                "not_reviewed",
                source_kind,
                json.dumps(normalized),
                raw_text,
                source_file_path,
                source_file_hash_sha256,
                now,
                now,
            ),
        )
        conn.commit()
    return product_id


def list_products(
    limit: int = 200,
    offset: int = 0,
    source_kind: str | None = None,
    product_type: str | None = None
) -> list[dict[str, Any]]:
    """
    List products with optional filtering.

    Args:
        limit: Maximum number of products to return
        offset: Number of products to skip
        source_kind: Filter by data source (e.g., 'akb_finanzportal', 'leonteq_api')
        product_type: Filter by product type (partial match, case-insensitive)

    Returns:
        List of product records
    """
    init_db()

    query = "SELECT * FROM products WHERE 1=1"
    params: list[Any] = []

    if source_kind:
        query += " AND source_kind = ?"
        params.append(source_kind)

    if product_type:
        query += " AND product_type LIKE ?"
        params.append(f"%{product_type}%")

    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def count_products(
    source_kind: str | None = None,
    product_type: str | None = None
) -> int:
    """
    Count products with optional filtering.

    Args:
        source_kind: Filter by data source
        product_type: Filter by product type (partial match, case-insensitive)

    Returns:
        Total count of matching products
    """
    init_db()

    query = "SELECT COUNT(*) AS count FROM products WHERE 1=1"
    params: list[Any] = []

    if source_kind:
        query += " AND source_kind = ?"
        params.append(source_kind)

    if product_type:
        query += " AND product_type LIKE ?"
        params.append(f"%{product_type}%")

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()

    return int(row["count"])


def clear_products() -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM products")
        conn.commit()


def get_product(product_id: str) -> dict[str, Any] | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return dict(row) if row else None


def update_review_status(product_id: str, status: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET review_status = ?, updated_at = ? WHERE id = ?",
            (status, _utc_now(), product_id),
        )
        conn.commit()


def update_source_file_path(product_id: str, source_file_path: str | None) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET source_file_path = ?, updated_at = ? WHERE id = ?",
            (source_file_path, _utc_now(), product_id),
        )
        conn.commit()


def create_crawl_run(name: str) -> str:
    init_db()
    run_id = str(uuid4())
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO crawl_runs (id, name, status, total, completed, errors_count, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, name, "running", 0, 0, 0, now, now),
        )
        conn.commit()
    return run_id


def get_crawl_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def update_crawl_run(
    run_id: str,
    *,
    status: str | None = None,
    total: int | None = None,
    completed: int | None = None,
    errors_count: int | None = None,
    last_error: str | None = None,
    checkpoint_offset: int | None = None,
) -> None:
    init_db()
    updates = []
    params: list[Any] = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if total is not None:
        updates.append("total = ?")
        params.append(total)
    if completed is not None:
        updates.append("completed = ?")
        params.append(completed)
    if errors_count is not None:
        updates.append("errors_count = ?")
        params.append(errors_count)
    if last_error is not None:
        updates.append("last_error = ?")
        params.append(last_error)
    if checkpoint_offset is not None:
        updates.append("checkpoint_offset = ?")
        params.append(checkpoint_offset)
    updates.append("updated_at = ?")
    params.append(_utc_now())

    if status in {"completed", "failed"}:
        updates.append("ended_at = ?")
        params.append(_utc_now())

    params.append(run_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE crawl_runs SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()


def increment_crawl_completed(run_id: str, delta: int = 1) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE crawl_runs SET completed = completed + ?, updated_at = ? WHERE id = ?",
            (delta, _utc_now(), run_id),
        )
        conn.commit()


def increment_crawl_errors(run_id: str, error_message: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE crawl_runs
            SET errors_count = errors_count + 1, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (error_message, _utc_now(), run_id),
        )
        conn.commit()


def pause_crawl_run(run_id: str) -> None:
    """Pause a running crawl."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE crawl_runs SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
            ("paused", _utc_now(), run_id, "running"),
        )
        conn.commit()


def resume_crawl_run(run_id: str) -> None:
    """Resume a paused crawl."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE crawl_runs SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
            ("running", _utc_now(), run_id, "paused"),
        )
        conn.commit()


def cancel_crawl_run(run_id: str) -> None:
    """Cancel a running or paused crawl."""
    init_db()
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE crawl_runs SET status = ?, updated_at = ?, ended_at = ? WHERE id = ? AND status IN (?, ?)",
            ("cancelled", now, now, run_id, "running", "paused"),
        )
        conn.commit()


def is_crawl_paused(run_id: str) -> bool:
    """Check if a crawl is paused."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM crawl_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    return row["status"] == "paused" if row else False


def is_crawl_cancelled(run_id: str) -> bool:
    """Check if a crawl has been cancelled."""
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM crawl_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    return row["status"] == "cancelled" if row else False


def get_products_for_pdf_enrichment(source_kind: str = "leonteq_api", limit: int = 100) -> list[dict[str, Any]]:
    """
    Get products that need PDF enrichment (missing coupon data).

    Args:
        source_kind: Data source to filter by
        limit: Maximum number of products to return

    Returns:
        List of product records with id, raw_text, and normalized_json
    """
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, raw_text, normalized_json
            FROM products
            WHERE source_kind = ?
              AND (
                json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
                OR json_extract(normalized_json, '$.barrier_level_pct.value') IS NULL
              )
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (source_kind, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def update_product_normalized_json(product_id: int, normalized_json: str) -> None:
    """Update the normalized_json field for a product."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET normalized_json = ?, updated_at = ? WHERE id = ?",
            (normalized_json, _utc_now(), product_id),
        )
        conn.commit()


def update_product_raw_text(product_id: int, raw_text: str) -> None:
    """Update the raw_text field for a product."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE products SET raw_text = ?, updated_at = ? WHERE id = ?",
            (raw_text, _utc_now(), product_id),
        )
        conn.commit()
