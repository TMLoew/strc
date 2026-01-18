"""
Diagnostic script to find products with invalid JSON in normalized_json field.

This helps identify database records that need cleanup.
"""

import json
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import get_connection, init_db


def check_invalid_json():
    """Check all products for invalid JSON in normalized_json field."""
    init_db()

    query = """
        SELECT id, isin, source_kind, normalized_json
        FROM products
        ORDER BY id
    """

    with get_connection() as conn:
        rows = conn.execute(query).fetchall()

    total = len(rows)
    invalid_count = 0
    invalid_products = []

    print(f"Checking {total} products for invalid JSON...\n")

    for row in rows:
        product_id = row["id"]
        isin = row["isin"] or "N/A"
        source_kind = row["source_kind"]
        normalized_json = row["normalized_json"]

        # Skip empty/null
        if not normalized_json:
            continue

        # Try to parse
        try:
            json.loads(normalized_json)
        except json.JSONDecodeError as e:
            invalid_count += 1
            invalid_products.append({
                "id": product_id,
                "isin": isin,
                "source_kind": source_kind,
                "error": str(e),
                "preview": normalized_json[:100]  # First 100 chars
            })
            print(f"❌ Product {product_id} ({isin}) - {source_kind}")
            print(f"   Error: {e}")
            print(f"   Preview: {normalized_json[:100]}...\n")

    print("\n" + "=" * 60)
    print(f"RESULTS:")
    print(f"Total products: {total}")
    print(f"Invalid JSON: {invalid_count}")
    print(f"Valid JSON: {total - invalid_count}")
    print("=" * 60)

    if invalid_count > 0:
        print(f"\n⚠️  Found {invalid_count} products with invalid JSON!")
        print("\nRecommendation:")
        print("  1. Review the products above")
        print("  2. Use scripts/fix_invalid_json.py to repair them")
        print("  3. Or delete them if they're corrupted beyond repair")
        return 1
    else:
        print("\n✅ All products have valid JSON!")
        return 0


if __name__ == "__main__":
    sys.exit(check_invalid_json())
