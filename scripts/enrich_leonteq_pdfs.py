#!/usr/bin/env python3
"""
Script to enrich Leonteq API products with data from termsheet PDFs.

Usage:
    poetry run python scripts/enrich_leonteq_pdfs.py [--limit N] [--resume]

Examples:
    # Enrich up to 100 products
    poetry run python scripts/enrich_leonteq_pdfs.py

    # Enrich up to 500 products
    poetry run python scripts/enrich_leonteq_pdfs.py --limit 500

    # Resume from checkpoint after interruption
    poetry run python scripts/enrich_leonteq_pdfs.py --resume
"""

import argparse
import logging
import sys
from pathlib import Path

from backend.app.services.leonteq_pdf_enrichment import enrich_leonteq_products_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def progress_bar(current, total, message="", stats=None):
    """Display progress bar in terminal."""
    bar_length = 40
    progress = current / total if total > 0 else 0
    filled = int(bar_length * progress)
    bar = "█" * filled + "░" * (bar_length - filled)

    stats_str = ""
    if stats:
        stats_str = f" | ✓ {stats['enriched']} ✗ {stats['failed']}"

    # Use \r to overwrite the same line
    sys.stdout.write(f"\r[{bar}] {current}/{total} ({progress*100:.1f}%){stats_str} | {message}".ljust(100))
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Enrich Leonteq products from termsheet PDFs")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of products to process (default: 100)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint file"
    )
    args = parser.parse_args()

    checkpoint_file = Path("data/enrich_checkpoint.json")

    print(f"\n{'=' * 70}")
    print("LEONTEQ PDF ENRICHMENT SERVICE")
    print("=" * 70)
    print(f"Target: Up to {args.limit} products")
    print("Method: Download termsheets from product pages")
    print("Storage: PDFs downloaded temporarily and deleted immediately")
    print("=" * 70)
    print()

    if args.resume and checkpoint_file.exists():
        print("⚡ Resuming from checkpoint...\n")
    else:
        if checkpoint_file.exists():
            checkpoint_file.unlink()

    try:
        stats = enrich_leonteq_products_batch(
            limit=args.limit,
            progress_callback=progress_bar,
            checkpoint_file=checkpoint_file
        )

        # New line after progress bar
        print("\n")

        print("=" * 70)
        print("ENRICHMENT COMPLETE")
        print("=" * 70)
        print(f"Total Processed: {stats['processed']}")
        print(f"Successfully Enriched: {stats['enriched']} ✓")
        print(f"Failed: {stats['failed']} ✗")
        if stats.get('skipped', 0) > 0:
            print(f"Skipped: {stats['skipped']}")
        print("=" * 70)

        if stats['enriched'] > 0:
            success_rate = (stats['enriched'] / stats['processed'] * 100) if stats['processed'] > 0 else 0
            print(f"\n✅ Success rate: {success_rate:.1f}%")
            print(f"✅ {stats['enriched']} products now have enhanced data from PDFs")

        if stats['failed'] > 0:
            print(f"\n⚠️  {stats['failed']} products could not be enriched")
            print("   Check logs above for details")

        print("\n📁 No PDFs were permanently stored - all temp files deleted")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print(f"💾 Progress saved to: {checkpoint_file}")
        print("   Resume with: --resume flag")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        print(f"💾 Progress saved to: {checkpoint_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
