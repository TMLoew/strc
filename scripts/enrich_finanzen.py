#!/usr/bin/env python3
"""
CLI script to enrich products with data from finanzen.ch.

Fetches coupon rates, barriers, strikes, and other structured product data
from finanzen.ch product pages using browser automation.

Usage:
    poetry run python scripts/enrich_finanzen.py
    poetry run python scripts/enrich_finanzen.py --limit 500
    poetry run python scripts/enrich_finanzen.py --resume
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.finanzen_crawler_service import enrich_products_from_finanzen_batch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def progress_bar(current, total, message="", stats=None):
    """Display progress bar in terminal."""
    bar_length = 40
    progress = current / total if total > 0 else 0
    filled = int(bar_length * progress)
    bar = "█" * filled + "░" * (bar_length - filled)

    stats_str = ""
    if stats:
        stats_str = f" | ✓ {stats['enriched']} ✗ {stats['failed']}"

    sys.stdout.write(f"\r[{bar}] {current}/{total} ({progress*100:.1f}%){stats_str} | {message}".ljust(120))
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Enrich products from finanzen.ch")
    parser.add_argument("--limit", type=int, default=100, help="Number of products to process (default: 100)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument(
        "--filter",
        type=str,
        default="missing_coupon",
        choices=["missing_coupon", "missing_barrier", "missing_any", "all_with_isin"],
        help="Filter mode (default: missing_coupon)"
    )
    args = parser.parse_args()

    checkpoint_file = Path("data/finanzen_checkpoint.json") if args.resume else None

    # Display filter mode description
    filter_descriptions = {
        "missing_coupon": "Products missing coupon rates (RECOMMENDED)",
        "missing_barrier": "Products missing barrier data",
        "missing_any": "Products missing coupons OR barriers",
        "all_with_isin": "All products with ISINs"
    }

    print("=" * 70)
    print("FINANZEN.CH COUPON ENRICHMENT SERVICE")
    print("=" * 70)
    print(f"Target: Up to {args.limit} products")
    print(f"Filter: {filter_descriptions.get(args.filter, args.filter)}")
    print(f"Method: Scrape product pages from finanzen.ch")
    print(f"Fields: Coupons, barriers, strikes, caps, participation rates")
    print("=" * 70)
    print()

    try:
        stats = enrich_products_from_finanzen_batch(
            limit=args.limit,
            progress_callback=progress_bar,
            checkpoint_file=checkpoint_file,
            filter_mode=args.filter
        )

        print()  # New line after progress bar
        print()
        print("=" * 70)
        print("ENRICHMENT COMPLETE")
        print("=" * 70)
        print(f"Total Processed: {stats['processed']}")
        print(f"Successfully Enriched: {stats['enriched']} ✓")
        print(f"Failed: {stats['failed']} ✗")
        print("=" * 70)
        print()

        if stats['enriched'] > 0:
            success_rate = (stats['enriched'] / stats['processed']) * 100
            print(f"✅ Success rate: {success_rate:.1f}%")
            print(f"✅ {stats['enriched']} products now have enhanced data from finanzen.ch")
        else:
            print("⚠️  No products were enriched - they may already have complete data")

        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user - checkpoint saved")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Enrichment failed: {e}", exc_info=True)
        print(f"\n❌ Enrichment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
