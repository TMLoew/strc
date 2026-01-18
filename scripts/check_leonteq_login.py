#!/usr/bin/env python
from __future__ import annotations

import os


def main() -> int:
    username = os.getenv("LEONTEQ_USERNAME")
    password = os.getenv("LEONTEQ_PASSWORD")
    if not username or not password:
        print("Missing LEONTEQ_USERNAME/LEONTEQ_PASSWORD in env.")
        return 1
    print("Leonteq credentials present. Playwright login not implemented in MVP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
