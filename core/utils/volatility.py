from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yfinance as yf


def _cache_path() -> Path:
    data_dir = Path(os.getenv("SPA_DATA_DIR", "./data"))
    cache_dir = data_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "volatility.json"


def _load_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict) -> None:
    path = _cache_path()
    path.write_text(json.dumps(cache, indent=2))


def _annualized_volatility(prices) -> float | None:
    returns = prices.pct_change().dropna()
    if returns.empty:
        return None
    daily_vol = returns.std()
    return float(daily_vol * (252**0.5))


def _normalize_ticker(ticker: str) -> str:
    normalized = ticker.strip()
    if normalized.lower().endswith(" equity"):
        normalized = normalized[:-7]
    return normalized


def get_volatility_for_tickers(tickers: Iterable[str]) -> float | None:
    unique = sorted({_normalize_ticker(t) for t in tickers if t})
    if not unique:
        return None

    cache = _load_cache()
    cache_key = "|".join(unique)
    cached = cache.get(cache_key)
    if cached and cached.get("volatility") is not None:
        return cached["volatility"]

    try:
        data = yf.download(unique, period="1y", interval="1d", auto_adjust=True, progress=False)
    except Exception:
        return None

    vols: list[float] = []
    if isinstance(data, dict):
        return None

    if "Close" in data.columns:
        close = data["Close"]
        if hasattr(close, "columns"):
            for col in close.columns:
                vol = _annualized_volatility(close[col])
                if vol is not None:
                    vols.append(vol)
        else:
            vol = _annualized_volatility(close)
            if vol is not None:
                vols.append(vol)

    if not vols:
        return None

    avg_vol = sum(vols) / len(vols)
    cache[cache_key] = {
        "volatility": avg_vol,
        "tickers": unique,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _save_cache(cache)
    return avg_vol
