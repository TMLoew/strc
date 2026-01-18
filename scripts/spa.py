#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services import ingest_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="spa")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    args = parser.parse_args()

    if args.command == "ingest":
        ids = ingest_directory()
        print(f"Ingested {len(ids)} PDFs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
