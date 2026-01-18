#!/usr/bin/env python3
"""
Test Leonteq API response structure.

Usage:
    python scripts/test_leonteq_api.py
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.settings import settings
from core.sources.leonteq_api import fetch_products_page, parse_api_product

def main():
    if not settings.leonteq_api_token:
        print("ERROR: SPA_LEONTEQ_API_TOKEN not configured in .env")
        print("\nTo get a token:")
        print("1. Open https://structuredproducts-ch.leonteq.com in browser")
        print("2. Open DevTools > Network tab")
        print("3. Find /rfb-api/products request")
        print("4. Copy the 'Authorization: Bearer <token>' header value")
        print("5. Set SPA_LEONTEQ_API_TOKEN=<token> in .env")
        return 1

    print("Fetching first page from Leonteq API...")
    print(f"Token configured: {settings.leonteq_api_token[:50]}...")

    try:
        response = fetch_products_page(
            token=settings.leonteq_api_token,
            offset=0,
            page_size=1  # Just get one product
        )

        print(f"\n{'='*80}")
        print("API Response Structure:")
        print(f"{'='*80}\n")

        metadata = response.get("searchMetadata", {})
        print(f"Total products available: {metadata.get('totalHits', 0)}")
        print(f"Products in this page: {len(response.get('products', []))}\n")

        products = response.get("products", [])
        if products:
            product = products[0]

            print(f"{'='*80}")
            print("Sample Product JSON (first product):")
            print(f"{'='*80}\n")
            print(json.dumps(product, indent=2))

            print(f"\n{'='*80}")
            print("Available Top-Level Keys:")
            print(f"{'='*80}\n")
            for key in sorted(product.keys()):
                value = product[key]
                if isinstance(value, dict):
                    print(f"  {key:30s} (dict with {len(value)} keys): {list(value.keys())[:5]}")
                elif isinstance(value, list):
                    print(f"  {key:30s} (list with {len(value)} items)")
                else:
                    print(f"  {key:30s} = {str(value)[:60]}")

            print(f"\n{'='*80}")
            print("Testing Parser:")
            print(f"{'='*80}\n")

            try:
                parsed = parse_api_product(product)
                print(f"✓ Parser succeeded!")
                print(f"\nParsed fields:")
                print(f"  ISIN: {parsed.isin.value if parsed.isin else 'NOT FOUND'}")
                print(f"  Valor: {parsed.valor_number.value if parsed.valor_number else 'NOT FOUND'}")
                print(f"  Issuer: {parsed.issuer_name.value if parsed.issuer_name else 'NOT FOUND'}")
                print(f"  Currency: {parsed.currency.value if parsed.currency else 'NOT FOUND'}")
                print(f"  Product Type: {parsed.product_type.value if parsed.product_type else 'NOT FOUND'}")
                print(f"  Product Name: {parsed.product_name.value if parsed.product_name else 'NOT FOUND'}")
                print(f"  Maturity: {parsed.maturity_date.value if parsed.maturity_date else 'NOT FOUND'}")
                print(f"  Underlyings: {len(parsed.underlyings) if parsed.underlyings else 0}")
                if parsed.underlyings:
                    for i, u in enumerate(parsed.underlyings):
                        print(f"    [{i}] Name: {u.name.value if u.name else 'NOT FOUND'}")
                        print(f"    [{i}] Strike: {u.strike_level.value if u.strike_level else 'NOT FOUND'}")
                        print(f"    [{i}] Barrier: {u.barrier_level.value if u.barrier_level else 'NOT FOUND'}")
            except Exception as e:
                print(f"✗ Parser failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("No products returned!")

    except Exception as e:
        print(f"\n✗ API request failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
