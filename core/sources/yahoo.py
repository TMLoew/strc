from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from core.models import NormalizedProduct, make_field
from core.utils.text import truncate_excerpt


@dataclass
class YahooSearchResult:
    product: NormalizedProduct
    source_kind: str
    raw_json: str | None = None


def search_isin(isin: str) -> Optional[YahooSearchResult]:
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": isin}
    with httpx.Client(timeout=20.0) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    quotes = data.get("quotes", [])
    if not quotes:
        return None

    best = quotes[0]
    product = NormalizedProduct()
    product.isin = make_field(isin, 0.5, "yahoo_search", truncate_excerpt(isin))
    product.product_name = make_field(best.get("shortname"), 0.4, "yahoo_search")
    product.ticker_six = make_field(best.get("symbol"), 0.4, "yahoo_search")
    product.currency = make_field(best.get("currency"), 0.3, "yahoo_search")

    return YahooSearchResult(product=product, source_kind="yahoo_search", raw_json=response.text)
