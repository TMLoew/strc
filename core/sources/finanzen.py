from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from core.models import NormalizedProduct, make_field
from core.utils.text import normalize_whitespace, truncate_excerpt

FINANZEN_URL = "https://www.finanzen.ch/derivate"
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


@dataclass
class FinanzenFetchResult:
    product: NormalizedProduct
    source_kind: str
    raw_html: str | None = None


def fetch_html(isin: str) -> str:
    url = f"{FINANZEN_URL}/{isin.lower()}"
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _extract_label(soup: BeautifulSoup, label: str) -> Optional[str]:
    """Extract value from table row by label (case-insensitive)."""
    label_el = soup.find(string=re.compile(rf"^{re.escape(label)}$", re.I))
    if not label_el:
        return None
    td = label_el.find_parent("tr")
    if not td:
        return None
    cols = td.find_all("td")
    if len(cols) < 2:
        return None
    return normalize_whitespace(cols[1].get_text(" "))


def _extract_label_fuzzy(soup: BeautifulSoup, *labels: str) -> Optional[str]:
    """Extract value by trying multiple label variations."""
    for label in labels:
        value = _extract_label(soup, label)
        if value:
            return value
    return None


def parse_number_ch(text: str) -> Optional[float]:
    """Parse Swiss-formatted number (e.g., '1'234.56 or 1'234,56)."""
    if not text:
        return None
    # Remove Swiss thousands separator (')
    cleaned = text.replace("'", "").replace("'", "")
    # Handle both . and , as decimal separator
    cleaned = cleaned.replace(",", ".")
    # Extract first number
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def parse_html(html: str, isin: str) -> FinanzenFetchResult:
    """Parse finanzen.ch product page with enhanced coupon/barrier extraction."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ")
    product = NormalizedProduct()

    # Extract ISIN
    isin_match = ISIN_RE.search(text) or ISIN_RE.search(isin)
    if isin_match:
        product.isin = make_field(
            isin_match.group(0), 0.7, "finanzen_html", truncate_excerpt(isin_match.group(0))
        )
    else:
        product.isin = make_field(isin, 0.6, "finanzen_html", truncate_excerpt(isin))

    # Extract issuer
    issuer = _extract_label_fuzzy(soup, "Emittent", "Issuer")
    if issuer:
        product.issuer_name = make_field(issuer, 0.6, "finanzen_html", truncate_excerpt(issuer))

    # Extract currency
    currency = _extract_label_fuzzy(soup, "Währung", "Currency")
    if currency:
        product.currency = make_field(currency, 0.7, "finanzen_html", truncate_excerpt(currency))

    # Extract product name
    product_name = soup.find("h1")
    if product_name:
        name = normalize_whitespace(product_name.get_text(" "))
        product.product_name = make_field(name, 0.6, "finanzen_html", truncate_excerpt(name))

    # Extract product type
    product_type = _extract_label_fuzzy(soup, "Produkttyp", "Typ", "Type", "Kategorie")
    if product_type:
        product.product_type = make_field(product_type, 0.6, "finanzen_html", truncate_excerpt(product_type))

    # CRITICAL: Extract coupon rate (multiple variations)
    coupon_text = _extract_label_fuzzy(
        soup,
        "Kupon",
        "Coupon",
        "Zinssatz",
        "Coupon p.a.",
        "Verzinsung",
        "Nominalzins",
        "Zinsen"
    )
    if coupon_text:
        # Try to parse percentage
        coupon_match = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*%', coupon_text)
        if coupon_match:
            coupon_value = parse_number_ch(coupon_match.group(1))
            if coupon_value is not None:
                product.coupon_rate_pct_pa = make_field(
                    coupon_value, 0.8, "finanzen_html", truncate_excerpt(coupon_text)
                )

    # Extract barrier level
    barrier_text = _extract_label_fuzzy(
        soup,
        "Barriere",
        "Barrier",
        "Knock-In",
        "Knock-In Barriere",
        "Barriere-Level"
    )
    if barrier_text:
        barrier_value = parse_number_ch(barrier_text)
        if barrier_value is not None:
            # Check if it's a percentage or absolute value
            if '%' in barrier_text or barrier_value <= 100:
                # Store as percentage of initial
                if not product.underlyings:
                    from core.models import Underlying
                    product.underlyings = [Underlying()]
                product.underlyings[0].barrier_pct_of_initial = make_field(
                    barrier_value, 0.7, "finanzen_html", truncate_excerpt(barrier_text)
                )
            else:
                # Store as absolute level
                if not product.underlyings:
                    from core.models import Underlying
                    product.underlyings = [Underlying()]
                product.underlyings[0].barrier_level = make_field(
                    barrier_value, 0.7, "finanzen_html", truncate_excerpt(barrier_text)
                )

    # Extract strike price
    strike_text = _extract_label_fuzzy(
        soup,
        "Strike",
        "Basispreis",
        "Ausübungspreis",
        "Strike Level"
    )
    if strike_text:
        strike_value = parse_number_ch(strike_text)
        if strike_value is not None:
            product.strike_price = make_field(
                strike_value, 0.7, "finanzen_html", truncate_excerpt(strike_text)
            )

    # Extract cap level
    cap_text = _extract_label_fuzzy(
        soup,
        "Cap",
        "Höchstbetrag",
        "Maximum",
        "Cap Level"
    )
    if cap_text:
        cap_value = parse_number_ch(cap_text)
        if cap_value is not None:
            product.cap_level_pct = make_field(
                cap_value, 0.7, "finanzen_html", truncate_excerpt(cap_text)
            )

    # Extract participation rate
    participation_text = _extract_label_fuzzy(
        soup,
        "Partizipation",
        "Partizipationsrate",
        "Participation",
        "Participation Rate"
    )
    if participation_text:
        participation_value = parse_number_ch(participation_text)
        if participation_value is not None:
            product.participation_rate_pct = make_field(
                participation_value, 0.7, "finanzen_html", truncate_excerpt(participation_text)
            )

    # Extract maturity date
    maturity_text = _extract_label_fuzzy(
        soup,
        "Verfall",
        "Fälligkeit",
        "Laufzeitende",
        "Maturity"
    )
    if maturity_text:
        # Try to parse date (DD.MM.YYYY format common in Switzerland)
        date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', maturity_text)
        if date_match:
            day, month, year = date_match.groups()
            iso_date = f"{year}-{int(month):02d}-{int(day):02d}"
            product.maturity_date = make_field(
                iso_date, 0.7, "finanzen_html", truncate_excerpt(maturity_text)
            )

    # Extract issue date
    issue_text = _extract_label_fuzzy(
        soup,
        "Ausgabedatum",
        "Emissionsdatum",
        "Issue Date",
        "Emission"
    )
    if issue_text:
        date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', issue_text)
        if date_match:
            day, month, year = date_match.groups()
            iso_date = f"{year}-{int(month):02d}-{int(day):02d}"
            product.issue_date = make_field(
                iso_date, 0.7, "finanzen_html", truncate_excerpt(issue_text)
            )

    return FinanzenFetchResult(product=product, source_kind="finanzen_html", raw_html=html)
