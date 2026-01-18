from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from core.utils.cache import read_cached_source, write_cached_source

AKB_URL = "https://www.akb.ch/firmen/anlagen/anlageprodukte/strukturierte-produkte"
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


def fetch_akb_html() -> str:
    cached = read_cached_source("akb", "catalog")
    if cached:
        return cached
    with httpx.Client(timeout=20.0) as client:
        response = client.get(AKB_URL)
        response.raise_for_status()
        html = response.text
    write_cached_source("akb", "catalog", html)
    return html


def parse_akb_isins(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ")
    isins = sorted({match.group(0) for match in ISIN_RE.finditer(text)})
    return isins
