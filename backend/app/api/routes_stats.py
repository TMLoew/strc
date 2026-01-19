from typing import Any

from fastapi import APIRouter

from backend.app.db.session import get_connection

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
def get_statistics() -> dict[str, Any]:
    """
    Get comprehensive database statistics.

    Returns statistics including:
    - Total products by source
    - Products by type
    - Products by currency
    - Products by issuer
    - Time-based statistics
    - Data quality metrics
    """
    with get_connection() as conn:
        # Total products
        total_result = conn.execute("SELECT COUNT(*) as count FROM products").fetchone()
        total_products = total_result["count"]

        # Products by source
        source_rows = conn.execute("""
            SELECT source_kind, COUNT(*) as count
            FROM products
            GROUP BY source_kind
            ORDER BY count DESC
        """).fetchall()

        products_by_source = [
            {"source": row["source_kind"], "count": row["count"]}
            for row in source_rows
        ]

        # Products by type (top 15)
        type_rows = conn.execute("""
            SELECT product_type, COUNT(*) as count
            FROM products
            WHERE product_type IS NOT NULL
            GROUP BY product_type
            ORDER BY count DESC
            LIMIT 15
        """).fetchall()

        products_by_type = [
            {"type": row["product_type"], "count": row["count"]}
            for row in type_rows
        ]

        # Products by currency
        currency_rows = conn.execute("""
            SELECT currency, COUNT(*) as count
            FROM products
            WHERE currency IS NOT NULL
            GROUP BY currency
            ORDER BY count DESC
        """).fetchall()

        products_by_currency = [
            {"currency": row["currency"], "count": row["count"]}
            for row in currency_rows
        ]

        # Products by issuer (top 10)
        issuer_rows = conn.execute("""
            SELECT issuer_name, COUNT(*) as count
            FROM products
            WHERE issuer_name IS NOT NULL
            GROUP BY issuer_name
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

        products_by_issuer = [
            {"issuer": row["issuer_name"], "count": row["count"]}
            for row in issuer_rows
        ]

        # Products by review status
        review_rows = conn.execute("""
            SELECT review_status, COUNT(*) as count
            FROM products
            GROUP BY review_status
            ORDER BY count DESC
        """).fetchall()

        products_by_review_status = [
            {"status": row["review_status"], "count": row["count"]}
            for row in review_rows
        ]

        # Products added today
        added_today = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE DATE(created_at) = DATE('now')
        """).fetchone()["count"]

        # Products added this week
        added_week = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE created_at >= DATE('now', '-7 days')
        """).fetchone()["count"]

        # Products added this month
        added_month = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE created_at >= DATE('now', 'start of month')
        """).fetchone()["count"]

        # Data quality metrics
        has_isin = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE isin IS NOT NULL
        """).fetchone()["count"]

        has_maturity = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE maturity_date IS NOT NULL
        """).fetchone()["count"]

        has_coupon = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL
        """).fetchone()["count"]

        has_underlyings = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE json_extract(normalized_json, '$.underlyings') != '[]'
              AND json_extract(normalized_json, '$.underlyings') IS NOT NULL
        """).fetchone()["count"]

        has_barrier = conn.execute("""
            SELECT COUNT(*) as count
            FROM products
            WHERE json_extract(normalized_json, '$.barrier_type.value') IS NOT NULL
               OR json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NOT NULL
        """).fetchone()["count"]

        # Maturity distribution (upcoming)
        maturity_rows = conn.execute("""
            SELECT
                CASE
                    WHEN maturity_date < DATE('now') THEN 'Expired'
                    WHEN maturity_date < DATE('now', '+3 months') THEN 'Next 3 months'
                    WHEN maturity_date < DATE('now', '+6 months') THEN '3-6 months'
                    WHEN maturity_date < DATE('now', '+1 year') THEN '6-12 months'
                    WHEN maturity_date < DATE('now', '+2 years') THEN '1-2 years'
                    ELSE '2+ years'
                END as maturity_bucket,
                COUNT(*) as count
            FROM products
            WHERE maturity_date IS NOT NULL
            GROUP BY maturity_bucket
            ORDER BY
                CASE maturity_bucket
                    WHEN 'Expired' THEN 0
                    WHEN 'Next 3 months' THEN 1
                    WHEN '3-6 months' THEN 2
                    WHEN '6-12 months' THEN 3
                    WHEN '1-2 years' THEN 4
                    ELSE 5
                END
        """).fetchall()

        maturity_distribution = [
            {"bucket": row["maturity_bucket"], "count": row["count"]}
            for row in maturity_rows
        ]

        # Crawl runs summary
        crawl_runs = conn.execute("""
            SELECT
                status,
                COUNT(*) as count,
                SUM(completed) as total_completed,
                SUM(errors_count) as total_errors
            FROM crawl_runs
            GROUP BY status
            ORDER BY count DESC
        """).fetchall()

        crawl_summary = [
            {
                "status": row["status"],
                "count": row["count"],
                "total_completed": row["total_completed"],
                "total_errors": row["total_errors"]
            }
            for row in crawl_runs
        ]

        # Recent crawl activity
        recent_crawls = conn.execute("""
            SELECT
                name,
                status,
                total,
                completed,
                errors_count,
                started_at,
                ended_at
            FROM crawl_runs
            ORDER BY started_at DESC
            LIMIT 5
        """).fetchall()

        recent_crawl_activity = [
            {
                "name": row["name"],
                "status": row["status"],
                "total": row["total"],
                "completed": row["completed"],
                "errors": row["errors_count"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"]
            }
            for row in recent_crawls
        ]

    return {
        "overview": {
            "total_products": total_products,
            "added_today": added_today,
            "added_this_week": added_week,
            "added_this_month": added_month
        },
        "by_source": products_by_source,
        "by_type": products_by_type,
        "by_currency": products_by_currency,
        "by_issuer": products_by_issuer,
        "by_review_status": products_by_review_status,
        "maturity_distribution": maturity_distribution,
        "data_quality": {
            "has_isin": {"count": has_isin, "percentage": round((has_isin / total_products) * 100, 1) if total_products > 0 else 0},
            "has_maturity": {"count": has_maturity, "percentage": round((has_maturity / total_products) * 100, 1) if total_products > 0 else 0},
            "has_coupon": {"count": has_coupon, "percentage": round((has_coupon / total_products) * 100, 1) if total_products > 0 else 0},
            "has_underlyings": {"count": has_underlyings, "percentage": round((has_underlyings / total_products) * 100, 1) if total_products > 0 else 0},
            "has_barrier": {"count": has_barrier, "percentage": round((has_barrier / total_products) * 100, 1) if total_products > 0 else 0}
        },
        "crawl_summary": crawl_summary,
        "recent_crawl_activity": recent_crawl_activity
    }
