"""
Fix products with invalid JSON in normalized_json field.

This script will:
1. Find all products with invalid JSON
2. Reset their normalized_json to empty dict {}
3. Log the changes for review
"""

import json
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import get_connection, init_db


def fix_invalid_json(dry_run: bool = True):
    """
    Fix products with invalid JSON in normalized_json field.

    Args:
        dry_run: If True, only report what would be fixed without making changes
    """
    init_db()

    query = """
        SELECT id, isin, source_kind, normalized_json
        FROM products
        ORDER BY id
    """

    with get_connection() as conn:
        rows = conn.execute(query).fetchall()

    total = len(rows)
    invalid_products = []

    print(f"Checking {total} products for invalid JSON...\n")

    for row in rows:
        product_id = row["id"]
        isin = row["isin"] or "N/A"
        source_kind = row["source_kind"]
        normalized_json = row["normalized_json"]

        # Skip empty/null (these are fine)
        if not normalized_json:
            continue

        # Try to parse
        try:
            json.loads(normalized_json)
        except json.JSONDecodeError as e:
            invalid_products.append({
                "id": product_id,
                "isin": isin,
                "source_kind": source_kind,
                "error": str(e),
                "preview": normalized_json[:100]
            })

    if not invalid_products:
        print("✅ No invalid JSON found! Database is clean.")
        return 0

    print(f"Found {len(invalid_products)} products with invalid JSON:\n")
    for product in invalid_products:
        print(f"  Product {product['id']} ({product['isin']}) - {product['source_kind']}")
        print(f"    Error: {product['error']}")
        print(f"    Preview: {product['preview']}...\n")

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No changes made")
        print("=" * 60)
        print(f"\nTo fix these {len(invalid_products)} products, run:")
        print("  poetry run python scripts/fix_invalid_json.py --apply")
        return 0

    # Apply fixes
    print("\n" + "=" * 60)
    print("APPLYING FIXES...")
    print("=" * 60)

    with get_connection() as conn:
        for product in invalid_products:
            product_id = product["id"]
            isin = product["isin"]

            # Reset to empty dict
            conn.execute(
                "UPDATE products SET normalized_json = ? WHERE id = ?",
                ("{}", product_id)
            )
            print(f"✅ Fixed product {product_id} ({isin}) - reset to empty dict")

        conn.commit()

    print(f"\n✅ Fixed {len(invalid_products)} products!")
    print("\nNext steps:")
    print("  1. Run enrichment to re-populate data for these products")
    print("  2. poetry run python scripts/enrich_finanzen.py --limit 100")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fix products with invalid JSON")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply fixes (default is dry-run mode)"
    )
    args = parser.parse_args()

    sys.exit(fix_invalid_json(dry_run=not args.apply))
