#!/usr/bin/env python3
"""
Monitor crawl progress in real-time.

Usage:
    python scripts/monitor_crawl.py <run_id>
    python scripts/monitor_crawl.py --latest
    python scripts/monitor_crawl.py --list
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db import models
from backend.app.settings import settings


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def print_crawl_status(run: dict, show_details: bool = True):
    """Print formatted crawl status."""
    status_emoji = {
        "running": "🔄",
        "completed": "✅",
        "failed": "❌"
    }

    emoji = status_emoji.get(run["status"], "❓")

    print(f"\n{emoji} Crawl: {run['name']} (ID: {run['id'][:8]}...)")
    print(f"   Status: {run['status'].upper()}")
    print(f"   Progress: {run['completed']}/{run['total']} ({run['completed']/run['total']*100:.1f}%)" if run['total'] > 0 else f"   Progress: {run['completed']} products")

    if run.get('errors_count', 0) > 0:
        print(f"   Errors: {run['errors_count']}")

    # Calculate duration
    from datetime import datetime
    started = datetime.fromisoformat(run['started_at'])

    if run['ended_at']:
        ended = datetime.fromisoformat(run['ended_at'])
        duration = (ended - started).total_seconds()
        print(f"   Duration: {format_duration(duration)}")
    else:
        now = datetime.utcnow()
        elapsed = (now - started).total_seconds()
        print(f"   Elapsed: {format_duration(elapsed)}")

        # Estimate completion
        if run['completed'] > 0 and run['total'] > 0:
            rate = run['completed'] / elapsed
            remaining = run['total'] - run['completed']
            eta_seconds = remaining / rate if rate > 0 else 0
            print(f"   ETA: {format_duration(eta_seconds)}")
            print(f"   Rate: {rate:.1f} products/sec")

    if show_details and run.get('last_error'):
        print(f"   Last Error: {run['last_error'][:100]}...")

    print()


def monitor_crawl(run_id: str, interval: float = 2.0):
    """Monitor a crawl in real-time."""
    print(f"Monitoring crawl: {run_id}")
    print("Press Ctrl+C to stop monitoring\n")

    try:
        while True:
            run = models.get_crawl_run(run_id)

            if not run:
                print(f"❌ Crawl not found: {run_id}")
                return

            # Clear screen (optional)
            # print("\033[H\033[J", end="")

            print_crawl_status(run)

            if run['status'] in ['completed', 'failed']:
                print("Crawl finished!")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


def list_recent_crawls(limit: int = 10):
    """List recent crawls."""
    import sqlite3

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM crawl_runs
        ORDER BY started_at DESC
        LIMIT ?
    """, (limit,))

    runs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not runs:
        print("No crawls found.")
        return

    print(f"\n📊 Recent Crawls (last {limit}):\n")

    for run in runs:
        print_crawl_status(run, show_details=False)


def get_latest_run() -> str | None:
    """Get the most recent crawl run ID."""
    import sqlite3

    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM crawl_runs
        ORDER BY started_at DESC
        LIMIT 1
    """)

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None


def show_products_by_source():
    """Show product counts by source."""
    import sqlite3

    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT source_kind, COUNT(*) as count
        FROM products
        GROUP BY source_kind
        ORDER BY count DESC
    """)

    results = cursor.fetchall()
    conn.close()

    if not results:
        print("No products in database.")
        return

    print("\n📦 Products by Source:\n")

    total = sum(count for _, count in results)

    for source, count in results:
        percentage = (count / total * 100) if total > 0 else 0
        print(f"   {source:20s}: {count:6d} ({percentage:5.1f}%)")

    print(f"\n   {'TOTAL':20s}: {total:6d}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Leonteq import and crawl progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Monitor specific crawl
    python scripts/monitor_crawl.py abc-123-def

    # Monitor latest crawl
    python scripts/monitor_crawl.py --latest

    # List recent crawls
    python scripts/monitor_crawl.py --list

    # Show product statistics
    python scripts/monitor_crawl.py --stats
        """
    )

    parser.add_argument("run_id", nargs="?", help="Crawl run ID to monitor")
    parser.add_argument("--latest", action="store_true", help="Monitor the latest crawl")
    parser.add_argument("--list", action="store_true", help="List recent crawls")
    parser.add_argument("--stats", action="store_true", help="Show product statistics")
    parser.add_argument("--interval", type=float, default=2.0, help="Refresh interval in seconds (default: 2.0)")

    args = parser.parse_args()

    if args.list:
        list_recent_crawls()
    elif args.stats:
        show_products_by_source()
    elif args.latest:
        run_id = get_latest_run()
        if run_id:
            monitor_crawl(run_id, args.interval)
        else:
            print("No crawls found in database.")
    elif args.run_id:
        monitor_crawl(args.run_id, args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
