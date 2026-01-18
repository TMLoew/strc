from __future__ import annotations

import re
import time
from typing import Any

import httpx

from core.utils.cache import read_cached_source, write_cached_source
from core.sources.swissquote import is_login_page

SCANNER_URL = "https://premium.swissquote.ch/trading-platform/#scanner"
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


def fetch_scanner_html(timeout_ms: int = 20000) -> str:
    cached = read_cached_source("swissquote_scanner", "scanner")
    if cached:
        return cached

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(SCANNER_URL, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()

    write_cached_source("swissquote_scanner", "scanner", html)
    return html


def extract_isins(html: str) -> list[str]:
    return sorted({match.group(0) for match in ISIN_RE.finditer(html)})


def fetch_scanner_isins(
    timeout_ms: int = 20000,
    username: str | None = None,
    password: str | None = None,
    storage_state: dict[str, Any] | None = None,
) -> list[str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    responses: list[str] = []

    def handle_response(response):
        try:
            if "application/json" in (response.headers.get("content-type") or ""):
                responses.append(response.text())
        except Exception:
            return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=storage_state) if storage_state else browser.new_context()
        page = context.new_page()
        page.on("response", handle_response)
        if username and password:
            page.goto("https://premium.swissquote.ch", wait_until="networkidle", timeout=timeout_ms)
            if "login" in page.title().lower():
                page.fill("input[name='username']", username)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']")
                page.wait_for_timeout(3000)
        page.goto(SCANNER_URL, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(3000)
        html = page.content()
        context.close()
        browser.close()

    combined = "\n".join(responses + [html])
    return extract_isins(combined)


def interactive_login_storage_state(timeout_ms: int = 300000) -> dict[str, Any]:
    """
    Interactive Swissquote login with browser automation.

    Opens a browser window for user to manually log in.
    Waits for successful login before capturing session state.

    Args:
        timeout_ms: Maximum time to wait for login (default: 5 minutes)

    Returns:
        Storage state dict with cookies and session data

    Raises:
        RuntimeError: If login times out or Playwright not available
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    print("Opening browser for Swissquote login...")
    print("Please log in manually. The browser will close automatically after successful login.")
    print(f"Timeout: {timeout_ms / 1000:.0f} seconds")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to scanner page (will redirect to login if needed)
        page.goto(SCANNER_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        deadline = time.time() + (timeout_ms / 1000)
        start_time = time.time()

        # Wait for actual login to complete
        # We need to wait at least 10 seconds before checking to give user time to login
        min_wait_time = 10

        while time.time() < deadline:
            elapsed = time.time() - start_time

            # Don't check login status for first 10 seconds (give user time to start logging in)
            if elapsed < min_wait_time:
                page.wait_for_timeout(2000)
                continue

            try:
                html = page.content()
                current_url = page.url or ""

                # Check for successful login indicators:
                # 1. URL contains trading-platform/#scanner (the actual scanner page)
                # 2. Page is not showing login form
                # 3. Page has loaded actual content (not just redirecting)

                is_on_scanner = "#scanner" in current_url and "trading-platform" in current_url
                has_login_form = is_login_page(html)

                # Additional check: look for scanner-specific content
                has_scanner_content = "scanner" in html.lower() and len(html) > 5000

                if is_on_scanner and not has_login_form and has_scanner_content:
                    # Wait a bit more to ensure session is fully established
                    page.wait_for_timeout(3000)

                    # Capture the session state
                    state = context.storage_state()

                    print(f"✓ Login successful! Session captured after {elapsed:.1f} seconds.")

                    context.close()
                    browser.close()
                    return state

            except Exception as e:
                # If there's an error checking, just continue waiting
                print(f"Waiting for login... ({elapsed:.0f}s elapsed)")

            page.wait_for_timeout(2000)

        # Timeout reached
        context.close()
        browser.close()

    raise RuntimeError("swissquote_login_timeout")


def fetch_scanner_html_fallback() -> str:
    cached = read_cached_source("swissquote_scanner", "scanner")
    if cached:
        return cached
    with httpx.Client(timeout=20.0) as client:
        response = client.get(SCANNER_URL)
        response.raise_for_status()
        html = response.text
    write_cached_source("swissquote_scanner", "scanner", html)
    return html
