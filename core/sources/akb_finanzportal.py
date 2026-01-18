from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup

from core.models import NormalizedProduct, make_field
from core.utils.cache import read_cached_source, write_cached_source
from core.utils.dates import parse_date_de
from core.utils.text import normalize_whitespace, parse_number_ch, truncate_excerpt

AKB_BASE_URL = "https://boerse.akb.ch/finanzportal"
MULTI_SEARCH_URL = f"{AKB_BASE_URL}/api/multi-search"
DETAIL_URL = f"{AKB_BASE_URL}/details"

DEFAULT_FIELDS = "M_NAME,M_SYMB,M_ISIN,M_MARKET:value:description,SC_GROUPED:value:description,M_CUR:value:description"
DEFAULT_FLAVOR = "DER"
DEFAULT_MARKET = "880"


@dataclass
class ListingEntry:
    listing_id: str
    isin: str | None
    name: str | None
    symbol: str | None
    currency: str | None
    market: str | None


def multi_search(
    search_term: str,
    market_ids: str = DEFAULT_MARKET,
    flavor: str = DEFAULT_FLAVOR,
    fields: str = DEFAULT_FIELDS,
    size: int = 15,
) -> dict[str, Any]:
    payload = {
        "searchTerm": search_term,
        "flavor": flavor,
        "fields": fields,
        "markets": market_ids,
        "mainMarket": "false",
        "useWildcards": "true",
        "size": str(size),
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(MULTI_SEARCH_URL, data=payload)
        response.raise_for_status()
        return response.json()


def extract_listings(response: dict[str, Any]) -> list[ListingEntry]:
    data = response.get("data") or {}
    categories = data.get("categories") or []
    listings: list[ListingEntry] = []
    for category in categories:
        for item in category.get("solidListings", []):
            listing_id = item.get("id", {}).get("value")
            if not listing_id:
                continue
            listings.append(
                ListingEntry(
                    listing_id=listing_id,
                    isin=item.get("M_ISIN", {}).get("value"),
                    name=item.get("M_NAME", {}).get("value"),
                    symbol=item.get("M_SYMB", {}).get("value"),
                    currency=item.get("M_CUR", {}).get("value"),
                    market=item.get("M_MARKET", {}).get("description"),
                )
            )
    return listings


def total_hits(response: dict[str, Any]) -> int:
    data = response.get("data") or {}
    return int(data.get("totalHits") or 0)


def fetch_detail_html(listing_id: str) -> str:
    cached = read_cached_source("akb_finanzportal", listing_id)
    if cached:
        return cached
    url = f"{DETAIL_URL}/{listing_id}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        html = response.text
    write_cached_source("akb_finanzportal", listing_id, html)
    return html


def _extract_label_value(soup: BeautifulSoup, label: str) -> str | None:
    th = soup.find("th", string=re.compile(rf"^{re.escape(label)}$", re.I))
    if not th:
        return None
    td = th.find_next_sibling("td")
    if not td:
        return None
    return normalize_whitespace(td.get_text(" "))


def parse_detail_html(html: str, listing_id: str) -> NormalizedProduct:
    soup = BeautifulSoup(html, "lxml")
    product = NormalizedProduct()

    issuer = _extract_label_value(soup, "Emittent")
    product_type = _extract_label_value(soup, "Typ")
    name = _extract_label_value(soup, "Name")
    maturity = _extract_label_value(soup, "Fälligkeit")
    last_trading = _extract_label_value(soup, "Letzter Handelstag")
    currency = _extract_label_value(soup, "Währung")
    isin = _extract_label_value(soup, "ISIN")
    valor = _extract_label_value(soup, "Valor")
    symbol = _extract_label_value(soup, "Symbol")
    exchange = _extract_label_value(soup, "Börse")
    issue_date = _extract_label_value(soup, "Emissionsdatum")
    denomination = _extract_label_value(soup, "Stückelung/Nennwert")
    eusipa_category = _extract_label_value(soup, "Eusipa Kategorie")
    eusipa_class = _extract_label_value(soup, "Eusipa Klass.")
    product_class = _extract_label_value(soup, "Produktklasse")

    if issuer:
        product.issuer_name = make_field(issuer, 0.8, "akb_finanzportal", truncate_excerpt(issuer))
    if product_type:
        product.product_type = make_field(product_type, 0.7, "akb_finanzportal", truncate_excerpt(product_type))
    if name:
        product.product_name = make_field(name, 0.7, "akb_finanzportal", truncate_excerpt(name))
    if currency:
        product.currency = make_field(currency, 0.7, "akb_finanzportal", truncate_excerpt(currency))
    if isin:
        product.isin = make_field(isin, 0.9, "akb_finanzportal", truncate_excerpt(isin))
    if valor:
        product.valor_number = make_field(valor, 0.8, "akb_finanzportal", truncate_excerpt(valor))
    if symbol:
        product.ticker_six = make_field(symbol, 0.6, "akb_finanzportal", truncate_excerpt(symbol))
    if exchange:
        product.listing_venue = make_field(exchange, 0.6, "akb_finanzportal", truncate_excerpt(exchange))
    if not product.product_type.value and eusipa_class:
        product.product_type = make_field(eusipa_class, 0.6, "akb_finanzportal", truncate_excerpt(eusipa_class))
    if not product.product_name.value and product_class:
        product.product_name = make_field(product_class, 0.5, "akb_finanzportal", truncate_excerpt(product_class))
    if eusipa_category:
        product.sspa_category = make_field(eusipa_category, 0.5, "akb_finanzportal", truncate_excerpt(eusipa_category))

    denomination_value = parse_number_ch(denomination) if denomination else None
    if denomination_value is not None:
        product.denomination = make_field(denomination_value, 0.6, "akb_finanzportal", truncate_excerpt(denomination))

    issue_date_iso = parse_date_de(issue_date) if issue_date else None
    if issue_date_iso:
        product.settlement_date = make_field(issue_date_iso, 0.6, "akb_finanzportal", truncate_excerpt(issue_date))

    maturity_iso = parse_date_de(maturity) if maturity else None
    if maturity_iso:
        product.maturity_date = make_field(maturity_iso, 0.7, "akb_finanzportal", truncate_excerpt(maturity))

    last_trading_iso = parse_date_de(last_trading) if last_trading else None
    if last_trading_iso:
        product.last_trading_day = make_field(last_trading_iso, 0.6, "akb_finanzportal", truncate_excerpt(last_trading))

    # Extract coupon rate from multiple sources (CRITICAL FIELD!)
    # Priority 1: Dedicated coupon field in table
    coupon_field = (
        _extract_label_value(soup, "Coupon") or
        _extract_label_value(soup, "Kupon") or
        _extract_label_value(soup, "Zinssatz") or
        _extract_label_value(soup, "Coupon Rate") or
        _extract_label_value(soup, "Coupon p.a.") or
        _extract_label_value(soup, "Verzinsung") or
        _extract_label_value(soup, "Zinsen")
    )

    if coupon_field:
        # Try to extract percentage from the field
        coupon_match = re.search(r'(\d+\.?\d*)\s*%', coupon_field)
        if coupon_match:
            coupon_value = float(coupon_match.group(1))
            product.coupon_rate_pct_pa = make_field(coupon_value, 0.9, "akb_finanzportal", truncate_excerpt(coupon_field))

    # Priority 2: Extract from product_class or name description (e.g., "5.10% p.a.")
    if not product.coupon_rate_pct_pa.value:
        description_text = product_class or name
        if description_text:
            coupon_match = re.search(r'(\d+\.?\d*)\s*%\s*p\.a\.', description_text, re.I)
            if coupon_match:
                coupon_value = float(coupon_match.group(1))
                product.coupon_rate_pct_pa = make_field(coupon_value, 0.7, "akb_finanzportal_class", truncate_excerpt(description_text))

    # Enhanced extraction from product_class (contains full description)
    description_text = product_class or name
    if description_text:

        # Extract underlyings from description (e.g., "auf Nestlé, Roche" or "auf Nestle, Roche")
        underlying_match = re.search(r'auf\s+(.+?)(?:\s*$|;|\()', description_text, re.I)
        if underlying_match:
            underlying_text = underlying_match.group(1).strip()
            # Split by commas to get individual underlyings
            underlying_names = [u.strip() for u in re.split(r',\s*(?:and\s+|und\s+)?', underlying_text)]

            # Store as underlyings list
            from core.models import Underlying
            for und_name in underlying_names:
                if und_name and len(und_name) > 2:  # Filter out empty/short strings
                    underlying = Underlying()
                    underlying.name = make_field(und_name, 0.6, "akb_finanzportal_class", truncate_excerpt(underlying_text))
                    product.underlyings.append(underlying)

        # Detect barrier type from description
        if re.search(r'barrier', description_text, re.I):
            product.barrier_type = make_field("barrier", 0.5, "akb_finanzportal_class", truncate_excerpt(description_text))

        # Detect autocallable
        if re.search(r'autocall', description_text, re.I):
            product.is_callable = make_field(True, 0.6, "akb_finanzportal_class", truncate_excerpt(description_text))

    # Try to extract barrier level from table (multiple field names)
    barrier_level = (
        _extract_label_value(soup, "Barriere") or
        _extract_label_value(soup, "Barrier") or
        _extract_label_value(soup, "Barriere Level") or
        _extract_label_value(soup, "Barriére") or
        _extract_label_value(soup, "Knock-In")
    )
    if barrier_level:
        barrier_value = parse_number_ch(barrier_level)
        if barrier_value is not None:
            # Check if it's a percentage or absolute value
            if '%' in barrier_level or barrier_value <= 100:
                # It's a percentage
                from core.models import Underlying
                if product.underlyings:
                    product.underlyings[0].barrier_pct_of_initial = make_field(
                        barrier_value, 0.7, "akb_finanzportal", truncate_excerpt(barrier_level)
                    )
            else:
                # It's an absolute value
                from core.models import Underlying
                if product.underlyings:
                    product.underlyings[0].barrier_level = make_field(
                        barrier_value, 0.7, "akb_finanzportal", truncate_excerpt(barrier_level)
                    )

    # Try to extract fixing dates
    initial_fixing = _extract_label_value(soup, "Anfangsfixierung")
    if not initial_fixing:
        initial_fixing = _extract_label_value(soup, "Initial Fixing")
    if initial_fixing:
        fixing_iso = parse_date_de(initial_fixing)
        if fixing_iso:
            product.initial_fixing_date = make_field(fixing_iso, 0.6, "akb_finanzportal", truncate_excerpt(initial_fixing))

    final_fixing = _extract_label_value(soup, "Schlussfixierung")
    if not final_fixing:
        final_fixing = _extract_label_value(soup, "Final Fixing")
    if final_fixing:
        fixing_iso = parse_date_de(final_fixing)
        if fixing_iso:
            product.final_fixing_date = make_field(fixing_iso, 0.6, "akb_finanzportal", truncate_excerpt(final_fixing))

    # Extract strike price/level
    strike = (
        _extract_label_value(soup, "Strike") or
        _extract_label_value(soup, "Ausübungspreis") or
        _extract_label_value(soup, "Basispreis") or
        _extract_label_value(soup, "Strike Level")
    )
    if strike:
        strike_value = parse_number_ch(strike)
        if strike_value is not None:
            from core.models import Underlying
            if product.underlyings:
                product.underlyings[0].strike_level = make_field(
                    strike_value, 0.7, "akb_finanzportal", truncate_excerpt(strike)
                )

    # Extract cap level
    cap = (
        _extract_label_value(soup, "Cap") or
        _extract_label_value(soup, "Höchstbetrag") or
        _extract_label_value(soup, "Maximum")
    )
    if cap:
        cap_value = parse_number_ch(cap)
        if cap_value is not None:
            if '%' in cap or cap_value <= 500:  # Likely a percentage
                product.cap_level_pct = make_field(cap_value, 0.7, "akb_finanzportal", truncate_excerpt(cap))

    # Extract participation rate
    participation = (
        _extract_label_value(soup, "Partizipation") or
        _extract_label_value(soup, "Partizipationsrate") or
        _extract_label_value(soup, "Participation") or
        _extract_label_value(soup, "Participation Rate")
    )
    if participation:
        participation_value = parse_number_ch(participation)
        if participation_value is not None:
            product.participation_rate_pct = make_field(
                participation_value, 0.7, "akb_finanzportal", truncate_excerpt(participation)
            )

    # Extract payment/coupon dates from tables
    # Look for tables with observation/payment dates
    tables = soup.find_all('table')
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all('th')]

        # Check if this is a coupon payment schedule
        if any('Coupon' in h or 'Zahlung' in h or 'Payment' in h for h in headers):
            rows = table.find_all('tr')[1:]  # Skip header row
            payment_dates = []

            for row in rows:
                cells = row.find_all('td')
                if cells:
                    # First cell often contains the date
                    date_text = cells[0].get_text(strip=True)
                    date_iso = parse_date_de(date_text)
                    if date_iso:
                        payment_dates.append(make_field(
                            date_iso, 0.6, "akb_finanzportal", truncate_excerpt(date_text)
                        ))

            if payment_dates and len(payment_dates) <= 50:  # Sanity check
                # Store as observation dates (for early redemption/autocall)
                product.call_observation_dates = payment_dates[:20]  # Limit to 20 dates

        # Check if this is an observation/autocall schedule
        if any('Beobachtung' in h or 'Observation' in h or 'Autocall' in h or 'Rückzahlung' in h for h in headers):
            rows = table.find_all('tr')[1:]
            observation_dates = []

            for row in rows:
                cells = row.find_all('td')
                if cells:
                    date_text = cells[0].get_text(strip=True)
                    date_iso = parse_date_de(date_text)
                    if date_iso:
                        observation_dates.append(make_field(
                            date_iso, 0.7, "akb_finanzportal", truncate_excerpt(date_text)
                        ))

            if observation_dates and len(observation_dates) <= 50:
                # These are early redemption dates
                product.call_observation_dates = observation_dates[:20]

    product.source_file_name = make_field(listing_id, 1.0, "akb_finanzportal")
    return product
