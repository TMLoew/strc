from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional, Any

import httpx
from bs4 import BeautifulSoup

from core.models import NormalizedProduct, make_field
from core.utils.text import truncate_excerpt

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")
VALOR_RE = re.compile(r"\b\d{6,9}\b")
CURRENCY_RE = re.compile(r"\b(CHF|EUR|USD|GBP|JPY)\b")


@dataclass
class LeonteqFetchResult:
    product: NormalizedProduct
    pdf_url: Optional[str]
    source_kind: str


BASE_URL = "https://structuredproducts-ch.leonteq.com"


def fetch_public_html(isin: str) -> str:
    url = f"{BASE_URL}/isin/{isin}"
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _parse_text_field(pattern: re.Pattern[str], text: str, source: str, confidence: float) -> Optional[dict]:
    match = pattern.search(text)
    if not match:
        return None
    excerpt = truncate_excerpt(match.group(0))
    return make_field(match.group(0), confidence, source, excerpt).model_dump()


def parse_public_html(html: str, isin: str) -> LeonteqFetchResult:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ")
    product = NormalizedProduct()

    isin_match = _parse_text_field(ISIN_RE, text, "leonteq_html_public", 0.8)
    if isin_match:
        product.isin = make_field(isin_match["value"], 0.8, "leonteq_html_public", isin_match["raw_excerpt"])
    else:
        product.isin = make_field(isin, 0.5, "leonteq_html_public", truncate_excerpt(isin))

    valor_match = _parse_text_field(VALOR_RE, text, "leonteq_html_public", 0.6)
    if valor_match:
        product.valor_number = make_field(valor_match["value"], 0.6, "leonteq_html_public", valor_match["raw_excerpt"])

    currency_match = _parse_text_field(CURRENCY_RE, text, "leonteq_html_public", 0.6)
    if currency_match:
        product.currency = make_field(currency_match["value"], 0.6, "leonteq_html_public", currency_match["raw_excerpt"])

    product.product_type = make_field(_find_label_value(text, "Product Type"), 0.6, "leonteq_html_public")
    product.issuer_name = make_field(_find_label_value(text, "Issuer"), 0.6, "leonteq_html_public")
    product.ticker_six = make_field(_find_label_value(text, "Ticker"), 0.5, "leonteq_html_public")
    product.settlement_type = make_field(_find_label_value(text, "Settlement"), 0.5, "leonteq_html_public")
    product.settlement_date = make_field(_find_label_value(text, "Issue Date"), 0.5, "leonteq_html_public")
    _apply_yield_from_text(product, text, "leonteq_html_public")

    pdf_url = _find_pdf_link(soup)
    return LeonteqFetchResult(product=product, pdf_url=pdf_url, source_kind="leonteq_html")


def _apply_yield_from_text(product: NormalizedProduct, text: str, source: str) -> None:
    ytm_match = re.search(
        r"(Yield to Maturity|YTM|Rendite bis (?:F[aä]lligkeit|Verfall))[^0-9%]{0,30}([0-9]+(?:[.,][0-9]+)?)\s*%",
        text,
        re.IGNORECASE,
    )
    if ytm_match:
        value = float(ytm_match.group(2).replace(",", "."))
        product.yield_to_maturity_pct_pa = make_field(value, 0.6, source, truncate_excerpt(ytm_match.group(0)))

    wty_match = re.search(
        r"(Worst[^\n%]{0,20}Yield|Yield to Worst|Worst to Yield|Worst-Case Rendite|Rendite im (?:Worst|Schlechtesten) ?Fall)[^0-9%]{0,30}([0-9]+(?:[.,][0-9]+)?)\s*%",
        text,
        re.IGNORECASE,
    )
    if wty_match:
        value = float(wty_match.group(2).replace(",", "."))
        product.worst_to_yield_pct_pa = make_field(value, 0.6, source, truncate_excerpt(wty_match.group(0)))


def _find_label_value(text: str, label: str) -> Optional[str]:
    pattern = re.compile(rf"{re.escape(label)}\s*[:\-]\s*([^\n]+)")
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


def _find_pdf_link(soup: BeautifulSoup) -> Optional[str]:
    for link in soup.find_all("a"):
        href = link.get("href") or ""
        if ".pdf" in href.lower():
            return str(httpx.URL(BASE_URL).join(href))
    return None


async def fetch_authenticated(isin: str) -> Optional[str]:
    return None


def _looks_like_login(html: str) -> bool:
    lowered = html.lower()
    if "password" in lowered and (
        "login" in lowered
        or "sign in" in lowered
        or "anmelden" in lowered
        or "anmeldung" in lowered
        or "einloggen" in lowered
    ):
        return True
    return False


def fetch_authenticated_html(isin: str, storage_state: dict[str, Any], timeout_ms: int = 20000) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    url = f"{BASE_URL}/isin/{isin}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=storage_state)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        html = page.content()
        context.close()
        browser.close()

    if _looks_like_login(html):
        raise RuntimeError("leonteq_not_authenticated")
    return html


def interactive_login_storage_state(timeout_ms: int = 300000) -> dict[str, Any]:
    """
    Interactive Leonteq login with browser automation.

    Opens browser for manual login and automatically captures:
    - Session cookies/storage state
    - JWT API token from network requests

    The API token is automatically saved to .env file for use by the API crawler.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Playwright not available") from exc

    captured_token = None

    def handle_request(request):
        """Capture Authorization header from API requests."""
        nonlocal captured_token

        # Look for API requests to /rfb-api/products
        if "/rfb-api/products" in request.url:
            headers = request.headers
            auth_header = headers.get("authorization") or headers.get("Authorization")

            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "").strip()
                if token and len(token) > 100:  # JWT tokens are long
                    captured_token = token
                    print(f"✓ API token captured automatically (length: {len(token)} chars)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Listen to all requests to capture API token
        page.on("request", handle_request)

        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        start_time = time.time()
        deadline = time.time() + (timeout_ms / 1000)
        while time.time() < deadline:
            html = page.content()
            cookies = context.cookies()
            has_session_cookie = any(
                cookie.get("domain", "").endswith("leonteq.com") and cookie.get("value")
                for cookie in cookies
            )
            if time.time() - start_time > 5 and has_session_cookie and not _looks_like_login(html):
                state = context.storage_state()

                # Save API token to .env if captured
                if captured_token:
                    try:
                        _save_token_to_env(captured_token)
                        print("✓ API token saved to .env file - API crawler is now ready!")
                    except Exception as e:
                        print(f"Warning: Could not save API token to .env: {e}")

                context.close()
                browser.close()
                return state
            page.wait_for_timeout(2000)
        context.close()
        browser.close()
    raise RuntimeError("leonteq_login_timeout")


def _save_token_to_env(token: str) -> None:
    """
    Save Leonteq API token to .env file.

    Args:
        token: JWT Bearer token to save
    """
    from pathlib import Path

    # Find .env file (navigate up from this file to project root)
    env_path = Path(__file__).parent.parent.parent / ".env"

    if not env_path.exists():
        # Create from example if available
        env_example = env_path.parent / ".env.example"
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_path)
        else:
            raise RuntimeError(".env file not found")

    # Read current content
    content = env_path.read_text()

    # Update or add token
    token_pattern = r'^SPA_LEONTEQ_API_TOKEN=.*$'
    token_line = f'SPA_LEONTEQ_API_TOKEN={token}'

    if re.search(token_pattern, content, re.MULTILINE):
        # Replace existing token
        new_content = re.sub(token_pattern, token_line, content, flags=re.MULTILINE)
    else:
        # Add token at the end
        if not content.endswith('\n'):
            content += '\n'
        new_content = content + f'\n{token_line}\n'

    # Write back
    env_path.write_text(new_content)
