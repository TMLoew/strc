from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from backend.app.db import models
from core.utils.volatility import get_volatility_for_tickers


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


PDF_RE = re.compile(r"https?://[^\s\"']+?\.pdf[^\s\"']*")
FACTSHEET_EN_RE = re.compile(r"https?://api\.factsheet-hub\.ch/[^\s\"']+\bl=en")


def _extract_english_termsheet(raw_text: str | None) -> str | None:
    if not raw_text:
        return None
    match = FACTSHEET_EN_RE.search(raw_text)
    if match:
        return match.group(0)
    match = PDF_RE.search(raw_text)
    return match.group(0) if match else None


def _time_to_maturity_days(maturity_date: str | None) -> int | None:
    parsed = _parse_date(maturity_date)
    if not parsed:
        return None
    return (parsed.date() - datetime.utcnow().date()).days


def _extract_tickers(normalized: dict[str, Any]) -> list[str]:
    tickers = []
    for underlying in normalized.get("underlyings", []):
        ticker = underlying.get("bloomberg_ticker", {}).get("value")
        if ticker:
            tickers.append(ticker)
    return tickers


def _risk_reward_score(normalized: dict[str, Any]) -> float | None:
    coupon = normalized.get("coupon_rate_pct_pa", {}).get("value")
    if coupon is None:
        return None

    tickers = _extract_tickers(normalized)
    vol = get_volatility_for_tickers(tickers) if tickers else None
    if vol is None or vol == 0:
        return None

    score = coupon / vol
    fx_risk = normalized.get("fx_risk_flag", {}).get("value")
    if fx_risk:
        score *= 0.9
    return score


def derived_metrics(normalized: dict[str, Any]) -> dict[str, Any]:
    maturity = normalized.get("maturity_date", {}).get("value")
    coupon = normalized.get("coupon_rate_pct_pa", {}).get("value")
    barrier = None
    if normalized.get("underlyings"):
        first = normalized["underlyings"][0]
        barrier = first.get("barrier_pct_of_initial", {}).get("value")
    barrier_buffer = None
    if barrier is not None:
        try:
            barrier_buffer = round(100 - float(barrier), 4)
        except (TypeError, ValueError):
            barrier_buffer = None
    tickers = _extract_tickers(normalized)
    volatility = get_volatility_for_tickers(tickers) if tickers else None
    score = _risk_reward_score(normalized)
    time_to_maturity_days = _time_to_maturity_days(maturity)
    time_to_maturity_years = None
    if time_to_maturity_days is not None:
        time_to_maturity_years = round(time_to_maturity_days / 365.0, 4)
    return {
        "time_to_maturity_days": time_to_maturity_days,
        "time_to_maturity_years": time_to_maturity_years,
        "coupon_vs_barrier_ratio": (coupon / barrier) if coupon and barrier else None,
        "worst_of": normalized.get("worst_of", {}).get("value"),
        "fx_risk_flag": normalized.get("fx_risk_flag", {}).get("value"),
        "volatility_annualized": volatility,
        "risk_reward_score": score,
        "coupon_rate_pct_pa": coupon,
        "barrier_pct_of_initial": barrier,
        "barrier_buffer_pct": barrier_buffer,
        "coupon_to_vol_ratio": (coupon / volatility) if coupon and volatility else None,
    }


def compare_products(ids: list[str]) -> dict[str, Any]:
    products = []
    for product_id in ids:
        record = models.get_product(product_id)
        if not record:
            continue
        normalized = json.loads(record["normalized_json"])
        products.append({"record": record, "normalized": normalized, "derived": derived_metrics(normalized)})
    return {"products": products}


def best_risk_reward(limit: int = 10) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for record in models.list_products():
        normalized = json.loads(record["normalized_json"])
        derived = derived_metrics(normalized)
        score = derived.get("risk_reward_score")
        if score is None:
            continue
        record["english_termsheet_url"] = _extract_english_termsheet(record.get("raw_text"))
        record.pop("raw_text", None)
        ranked.append({"record": record, "normalized": normalized, "derived": derived})

    ranked.sort(key=lambda item: item["derived"]["risk_reward_score"], reverse=True)
    return ranked[:limit]
