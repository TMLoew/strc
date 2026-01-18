#!/usr/bin/env python3
"""
View imported products from the database.

Usage:
    python scripts/view_products.py --latest 10
    python scripts/view_products.py --source leonteq_api
    python scripts/view_products.py --isin CH1234567890
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.settings import settings
import sqlite3


def format_field(field_data):
    """Format a Field[T] dict for display."""
    if not field_data or not isinstance(field_data, dict):
        return None

    value = field_data.get('value')
    confidence = field_data.get('confidence', 0)
    source = field_data.get('source', '')

    if value is None:
        return None

    return f"{value} (conf: {confidence:.2f}, src: {source})"


def print_product(product: dict, show_full: bool = False):
    """Print formatted product information."""
    normalized = json.loads(product['normalized_json'])

    print(f"\n{'='*80}")
    print(f"Product ID: {product['id']}")
    print(f"Source: {product['source_kind']}")
    print(f"Created: {product['created_at']}")
    print(f"{'='*80}\n")

    # Key fields
    print("📋 Identification:")
    if normalized.get('isin'):
        print(f"   ISIN: {format_field(normalized['isin'])}")
    if normalized.get('valor_number'):
        print(f"   Valor: {format_field(normalized['valor_number'])}")
    if normalized.get('ticker_six'):
        print(f"   Ticker: {format_field(normalized['ticker_six'])}")

    print("\n🏦 Issuer & Type:")
    if normalized.get('issuer_name'):
        print(f"   Issuer: {format_field(normalized['issuer_name'])}")
    if normalized.get('product_type'):
        print(f"   Type: {format_field(normalized['product_type'])}")
    if normalized.get('product_name'):
        print(f"   Name: {format_field(normalized['product_name'])}")

    print("\n💰 Financial:")
    if normalized.get('currency'):
        print(f"   Currency: {format_field(normalized['currency'])}")
    if normalized.get('denomination'):
        print(f"   Denomination: {format_field(normalized['denomination'])}")
    if normalized.get('coupon_rate_pct_pa'):
        print(f"   Coupon Rate: {format_field(normalized['coupon_rate_pct_pa'])}")
    if normalized.get('yield_to_maturity_pct_pa'):
        print(f"   YTM: {format_field(normalized['yield_to_maturity_pct_pa'])}")

    print("\n📅 Dates:")
    if normalized.get('settlement_date'):
        print(f"   Settlement: {format_field(normalized['settlement_date'])}")
    if normalized.get('maturity_date'):
        print(f"   Maturity: {format_field(normalized['maturity_date'])}")
    if normalized.get('initial_fixing_date'):
        print(f"   Initial Fixing: {format_field(normalized['initial_fixing_date'])}")

    print("\n📍 Listing:")
    if normalized.get('listing_venue'):
        print(f"   Venue: {format_field(normalized['listing_venue'])}")

    # Underlyings
    underlyings = normalized.get('underlyings', [])
    if underlyings:
        print("\n📊 Underlyings:")
        for i, underlying in enumerate(underlyings, 1):
            print(f"   {i}. {format_field(underlying.get('name', {}))}")
            if underlying.get('strike_level'):
                print(f"      Strike: {format_field(underlying['strike_level'])}")
            if underlying.get('barrier_level'):
                print(f"      Barrier: {format_field(underlying['barrier_level'])}")

    if show_full:
        print("\n📄 Full JSON:")
        print(json.dumps(normalized, indent=2))

    print()


def list_products(source: str | None = None, limit: int = 10, isin: str | None = None):
    """List products from database."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if isin:
        cursor.execute("""
            SELECT * FROM products
            WHERE isin = ?
            ORDER BY created_at DESC
        """, (isin,))
    elif source:
        cursor.execute("""
            SELECT * FROM products
            WHERE source_kind = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (source, limit))
    else:
        cursor.execute("""
            SELECT * FROM products
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

    products = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not products:
        print(f"No products found{f' for source {source}' if source else ''}.")
        return

    print(f"\n📦 Found {len(products)} product(s)\n")

    for product in products:
        print_product(product)


def search_products(query: str, limit: int = 10):
    """Search products by ISIN, Valor, or name."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM products
        WHERE isin LIKE ? OR valor_number LIKE ? OR product_name LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))

    products = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not products:
        print(f"No products found matching '{query}'.")
        return

    print(f"\n🔍 Found {len(products)} product(s) matching '{query}'\n")

    for product in products:
        print_product(product)


def show_statistics():
    """Show database statistics."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    # Total products
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]

    # By source
    cursor.execute("""
        SELECT source_kind, COUNT(*) as count
        FROM products
        GROUP BY source_kind
        ORDER BY count DESC
    """)
    by_source = cursor.fetchall()

    # By issuer (top 10)
    cursor.execute("""
        SELECT issuer_name, COUNT(*) as count
        FROM products
        WHERE issuer_name IS NOT NULL
        GROUP BY issuer_name
        ORDER BY count DESC
        LIMIT 10
    """)
    by_issuer = cursor.fetchall()

    # By currency
    cursor.execute("""
        SELECT currency, COUNT(*) as count
        FROM products
        WHERE currency IS NOT NULL
        GROUP BY currency
        ORDER BY count DESC
    """)
    by_currency = cursor.fetchall()

    # Recent imports
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM products
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 7
    """)
    recent = cursor.fetchall()

    conn.close()

    print(f"\n📊 Database Statistics\n")
    print(f"{'='*80}\n")

    print(f"Total Products: {total:,}\n")

    print("By Source:")
    for source, count in by_source:
        percentage = (count / total * 100) if total > 0 else 0
        print(f"   {source:20s}: {count:6,} ({percentage:5.1f}%)")

    if by_issuer:
        print("\nTop 10 Issuers:")
        for issuer, count in by_issuer:
            print(f"   {issuer:30s}: {count:6,}")

    if by_currency:
        print("\nBy Currency:")
        for currency, count in by_currency:
            print(f"   {currency:10s}: {count:6,}")

    if recent:
        print("\nRecent Imports (last 7 days):")
        for date, count in recent:
            print(f"   {date}: {count:6,} products")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="View imported products from database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # View latest 10 products
    python scripts/view_products.py --latest 10

    # View products from specific source
    python scripts/view_products.py --source leonteq_api --limit 5

    # View specific product by ISIN
    python scripts/view_products.py --isin CH1234567890

    # Search products
    python scripts/view_products.py --search "Leonteq"

    # Show statistics
    python scripts/view_products.py --stats
        """
    )

    parser.add_argument("--latest", type=int, metavar="N", help="Show latest N products")
    parser.add_argument("--source", help="Filter by source (e.g., leonteq_api, akb_html)")
    parser.add_argument("--isin", help="Show product with specific ISIN")
    parser.add_argument("--search", metavar="QUERY", help="Search products by ISIN, Valor, or name")
    parser.add_argument("--limit", type=int, default=10, help="Limit results (default: 10)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--full", action="store_true", help="Show full JSON for products")

    args = parser.parse_args()

    if args.stats:
        show_statistics()
    elif args.isin:
        list_products(isin=args.isin, limit=1)
    elif args.search:
        search_products(args.search, limit=args.limit)
    elif args.source:
        list_products(source=args.source, limit=args.limit)
    elif args.latest:
        list_products(limit=args.latest)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
