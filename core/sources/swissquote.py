from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from core.models import NormalizedProduct, make_field
from core.utils.text import truncate_excerpt

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


@dataclass
class SwissquoteFetchResult:
    product: NormalizedProduct
    source_kind: str
    raw_html: str | None = None


def is_login_page(html: str) -> bool:
    if not html:
        return False
    lowered = html.lower()
    return "login form" in lowered or "login to swissquote" in lowered or "auth_form" in lowered


def fetch_quote_html(isin: str) -> str:
    url = "https://trade.swissquote.ch/eding_trading-platform/"
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def fetch_quote_html_playwright(isin: str, timeout_ms: int = 20000) -> str:
    url = f"https://trade.swissquote.ch/eding_trading-platform/#fullQuote/{isin}/111_AUD"
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        content = page.content()
        browser.close()
    return content


def fetch_quote_html_playwright_auth(
    isin: str, username: str, password: str, timeout_ms: int = 20000
) -> str:
    url = f"https://trade.swissquote.ch/eding_trading-platform/#fullQuote/{isin}/111_AUD"
    login_url = "https://trade.swissquote.ch"
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(login_url, wait_until="networkidle", timeout=timeout_ms)
        if "login" in page.title().lower():
            page.fill("input[name='username']", username)
            page.fill("input[name='password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(3000)
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        content = page.content()
        browser.close()
    return content


def fetch_quote_html_playwright_session(isin: str, storage_state: dict) -> str:
    url = f"https://trade.swissquote.ch/eding_trading-platform/#fullQuote/{isin}/111_AUD"
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=storage_state)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        content = page.content()
        context.close()
        browser.close()
    return content


def parse_quote_html(html: str, isin: str) -> SwissquoteFetchResult:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ")
    product = NormalizedProduct()

    isin_match = ISIN_RE.search(text) or ISIN_RE.search(isin)
    if isin_match:
        excerpt = truncate_excerpt(isin_match.group(0))
        product.isin = make_field(isin_match.group(0), 0.4, "swissquote_html", excerpt)
    else:
        product.isin = make_field(isin, 0.3, "swissquote_html", truncate_excerpt(isin))

    product.source_file_name = make_field("swissquote_html", 1.0, "swissquote_html")
    return SwissquoteFetchResult(product=product, source_kind="swissquote_html", raw_html=html)
