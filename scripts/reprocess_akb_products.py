#!/usr/bin/env python3
"""
Re-process existing AKB products with enhanced parser.

This script:
1. Reads all AKB products from the database
2. Re-parses the cached HTML with the enhanced parser
3. Updates the database with newly extracted fields (coupon, underlyings, etc.)

Uses cached HTML so no API calls are needed - should be fast!
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sources.akb_finanzportal import parse_detail_html
from core.utils.hashing import sha256_text
from backend.app.db import models


def reprocess_akb_products(batch_size: int = 100):
    """Re-process all AKB products with enhanced parser."""

    # Get all AKB products
    conn = sqlite3.connect("data/structured_products.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, isin, source_file_hash_sha256, raw_text,
               json_extract(normalized_json, '$.source_file_name.value') as listing_id
        FROM products
        WHERE source_kind = 'akb_finanzportal'
    """)

    products = cursor.fetchall()
    total = len(products)
    conn.close()

    print(f"Found {total:,} AKB products to re-process")
    print(f"Processing in batches of {batch_size}...")

    updated_count = 0
    error_count = 0

    for i, (product_id, isin, source_hash, raw_html, listing_id) in enumerate(products):
        try:
            # Re-parse with enhanced parser
            enhanced_product = parse_detail_html(raw_html, listing_id or "unknown")

            # Update in database
            models.upsert_product(
                normalized=enhanced_product.model_dump(),
                raw_text=raw_html,
                source_kind="akb_finanzportal",
                source_file_path=None,
                source_file_hash_sha256=source_hash
            )

            updated_count += 1

            # Progress update
            if (i + 1) % batch_size == 0:
                pct = ((i + 1) / total) * 100
                print(f"  Progress: {i+1:,}/{total:,} ({pct:.1f}%) - {updated_count:,} updated, {error_count} errors")

        except Exception as exc:
            error_count += 1
            print(f"  ERROR processing {isin}: {exc}")

    # Final summary
    print(f"\n✓ Re-processing complete!")
    print(f"  Total: {total:,}")
    print(f"  Updated: {updated_count:,}")
    print(f"  Errors: {error_count}")

    # Show example of enhanced data
    if updated_count > 0:
        print(f"\nExample: Checking random product...")
        conn = sqlite3.connect("data/structured_products.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT isin,
                   json_extract(normalized_json, '$.coupon_rate_pct_pa.value') as coupon,
                   json_extract(normalized_json, '$.underlyings') as underlyings,
                   json_extract(normalized_json, '$.barrier_type.value') as barrier
            FROM products
            WHERE source_kind = 'akb_finanzportal'
              AND json_extract(normalized_json, '$.coupon_rate_pct_pa.value') IS NOT NULL
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        if row:
            isin, coupon, underlyings_json, barrier = row
            print(f"  ISIN: {isin}")
            print(f"  Coupon: {coupon}% p.a.")
            print(f"  Barrier: {barrier}")
            import json
            underlyings = json.loads(underlyings_json) if underlyings_json else []
            if underlyings:
                print(f"  Underlyings: {len(underlyings)}")
                for u in underlyings[:3]:
                    print(f"    - {u.get('name', {}).get('value', 'N/A')}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Re-process AKB products with enhanced parser")
    parser.add_argument("--batch-size", type=int, default=100, help="Progress update frequency")

    args = parser.parse_args()

    reprocess_akb_products(batch_size=args.batch_size)
