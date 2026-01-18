#!/usr/bin/env python3
"""
Check how many products are missing critical data fields.

Usage:
    poetry run python scripts/check_missing_data.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.db.session import get_connection, init_db


def check_missing_data():
    """Check and display statistics about missing data."""
    init_db()

    with get_connection() as conn:
        # Total products
        total = conn.execute("SELECT COUNT(*) as count FROM products").fetchone()["count"]

        # Products with ISINs
        with_isin = conn.execute(
            "SELECT COUNT(*) as count FROM products WHERE isin IS NOT NULL"
        ).fetchone()["count"]

        # Missing coupons
        missing_coupon = conn.execute("""
            SELECT COUNT(*) as count FROM products
            WHERE isin IS NOT NULL
              AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
        """).fetchone()["count"]

        # Missing barriers (both pct and absolute)
        missing_barrier = conn.execute("""
            SELECT COUNT(*) as count FROM products
            WHERE isin IS NOT NULL
              AND (
                json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
              )
        """).fetchone()["count"]

        # Missing either
        missing_any = conn.execute("""
            SELECT COUNT(*) as count FROM products
            WHERE isin IS NOT NULL
              AND (
                json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL
                OR (
                  json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NULL
                  AND json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NULL
                )
              )
        """).fetchone()["count"]

        # Products with coupons
        with_coupon = conn.execute("""
            SELECT COUNT(*) as count FROM products
            WHERE json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL
        """).fetchone()["count"]

        # Products with barriers
        with_barrier = conn.execute("""
            SELECT COUNT(*) as count FROM products
            WHERE (
              json_extract(normalized_json, '$.underlyings[0].barrier_pct_of_initial.value') IS NOT NULL
              OR json_extract(normalized_json, '$.underlyings[0].barrier_level.value') IS NOT NULL
            )
        """).fetchone()["count"]

        # Breakdown by source for missing coupons
        print()
        print("=" * 80)
        print("DATABASE DATA COMPLETENESS REPORT")
        print("=" * 80)
        print()
        print("OVERALL STATISTICS:")
        print(f"  Total products in database: {total:,}")
        print(f"  Products with ISINs: {with_isin:,}")
        print()
        print("COUPON COVERAGE:")
        print(f"  ✅ Products WITH coupons: {with_coupon:,} ({with_coupon/total*100:.1f}%)")
        print(f"  ❌ Products MISSING coupons: {total - with_coupon:,} ({(total-with_coupon)/total*100:.1f}%)")
        print(f"  ⚠️  With ISIN but missing coupon: {missing_coupon:,}")
        print()
        print("BARRIER COVERAGE:")
        print(f"  ✅ Products WITH barriers: {with_barrier:,} ({with_barrier/total*100:.1f}%)")
        print(f"  ❌ Products MISSING barriers: {total - with_barrier:,} ({(total-with_barrier)/total*100:.1f}%)")
        print(f"  ⚠️  With ISIN but missing barrier: {missing_barrier:,}")
        print()
        print("FINANZEN.CH ENRICHMENT TARGETS:")
        print(f"  🎯 missing_coupon filter: {missing_coupon:,} products")
        print(f"  🎯 missing_barrier filter: {missing_barrier:,} products")
        print(f"  🎯 missing_any filter: {missing_any:,} products")
        print(f"  🎯 all_with_isin filter: {with_isin:,} products")
        print()

        # Breakdown by source
        print("BREAKDOWN BY SOURCE (Missing Coupons):")
        print("-" * 80)

        source_stats = conn.execute("""
            SELECT
                source_kind,
                COUNT(*) as total,
                SUM(CASE WHEN json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NULL THEN 1 ELSE 0 END) as missing_coupon,
                SUM(CASE WHEN json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL THEN 1 ELSE 0 END) as has_coupon
            FROM products
            WHERE isin IS NOT NULL
            GROUP BY source_kind
            ORDER BY total DESC
        """).fetchall()

        for row in source_stats:
            source = row["source_kind"]
            total_src = row["total"]
            missing = row["missing_coupon"]
            has = row["has_coupon"]
            pct_missing = (missing / total_src * 100) if total_src > 0 else 0

            print(f"  {source:25s} | Total: {total_src:5,} | Missing: {missing:5,} ({pct_missing:5.1f}%) | Has: {has:5,}")

        print("=" * 80)
        print()

        if missing_coupon == 0:
            print("✅ ALL PRODUCTS WITH ISINs HAVE COUPONS!")
        else:
            print(f"💡 RECOMMENDATION: Run finanzen.ch crawler with 'missing_coupon' filter")
            print(f"   This will target {missing_coupon:,} products that need coupon data")

        print()


if __name__ == "__main__":
    check_missing_data()
