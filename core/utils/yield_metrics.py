from __future__ import annotations

from datetime import datetime
from typing import Any

from core.models import make_field
from core.utils.dates import parse_date_any


def _parse_percent(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _time_to_maturity_years(maturity_value: Any) -> float | None:
    if not maturity_value:
        return None
    if isinstance(maturity_value, str):
        parsed = parse_date_any(maturity_value)
        if parsed is None:
            return None
        try:
            maturity_date = datetime.strptime(parsed, "%Y-%m-%d")
        except ValueError:
            return None
    elif isinstance(maturity_value, datetime):
        maturity_date = maturity_value
    else:
        return None
    delta = maturity_date.date() - datetime.utcnow().date()
    years = delta.days / 365.0
    return years if years > 0 else None


def _approx_yield_pct(price_pct: float, coupon_pct: float, redemption_pct: float, years: float) -> float | None:
    if years <= 0:
        return None
    try:
        avg_price = (price_pct + redemption_pct) / 2.0
        if avg_price <= 0:
            return None
        annualized = (coupon_pct + (redemption_pct - price_pct) / years) / avg_price
        return round(annualized * 100, 4)
    except Exception:
        return None


def apply_yield_fields(normalized: dict[str, Any]) -> None:
    if not isinstance(normalized, dict):
        return

    coupon_pct = _parse_percent(normalized.get("coupon_rate_pct_pa", {}).get("value"))
    maturity_value = normalized.get("maturity_date", {}).get("value")
    years = _time_to_maturity_years(maturity_value)
    if coupon_pct is None or years is None:
        return

    issue_price = _parse_percent(normalized.get("issue_price_pct", {}).get("value"))
    assumed_par = False
    if issue_price is None:
        issue_price = 100.0
        assumed_par = True

    ytm_field = normalized.get("yield_to_maturity_pct_pa")
    if not (isinstance(ytm_field, dict) and ytm_field.get("value") is not None):
        ytm = _approx_yield_pct(issue_price, coupon_pct, 100.0, years)
        if ytm is not None:
            source = "derived_assumed_par" if assumed_par else "derived"
            confidence = 0.25 if assumed_par else 0.35
            normalized["yield_to_maturity_pct_pa"] = make_field(ytm, confidence, source).model_dump()

    wty_field = normalized.get("worst_to_yield_pct_pa")
    if isinstance(wty_field, dict) and wty_field.get("value") is not None:
        return

    barrier_pct = None
    underlyings = normalized.get("underlyings") or []
    if underlyings:
        barrier_pct = _parse_percent(underlyings[0].get("barrier_pct_of_initial", {}).get("value"))

    capital_protection = normalized.get("capital_protection", {}).get("value")
    redemption_worst = 100.0 if capital_protection else barrier_pct
    if redemption_worst is None:
        return

    wty = _approx_yield_pct(issue_price, coupon_pct, redemption_worst, years)
    if wty is not None:
        source = "derived_assumed_par" if assumed_par else "derived"
        confidence = 0.2 if assumed_par else 0.3
        normalized["worst_to_yield_pct_pa"] = make_field(wty, confidence, source).model_dump()
