from __future__ import annotations

import re
from pathlib import Path

from core.models import NormalizedProduct, make_field
from core.utils.text import truncate_excerpt

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")
VALOR_RE = re.compile(r"\b\d{6,9}\b")
CURRENCY_RE = re.compile(r"\b(CHF|EUR|USD|GBP|JPY)\b")
YTM_RE = re.compile(
    r"(Yield to Maturity|YTM|Rendite bis (?:F[aä]lligkeit|Verfall))[^0-9%]{0,30}([0-9]+(?:[.,][0-9]+)?)\s*%",
    re.IGNORECASE,
)
WTY_RE = re.compile(
    r"(Worst[^\n%]{0,20}Yield|Yield to Worst|Worst to Yield|Worst-Case Rendite|Rendite im (?:Worst|Schlechtesten) ?Fall)[^0-9%]{0,30}([0-9]+(?:[.,][0-9]+)?)\s*%",
    re.IGNORECASE,
)

# Date patterns
DATE_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b")  # DD.MM.YYYY or DD/MM/YYYY
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")  # YYYY-MM-DD

# Early redemption / observation date patterns
OBSERVATION_SECTION_RE = re.compile(
    r"(Early Redemption|Vorzeitige R[uü]ckzahlung|Autocall|Auto[- ]?Call|Observation|Beobachtung|Bewertung)[^:]{0,100}[:\n](.*?)(?=\n\n|\n[A-Z][a-z]+:|$)",
    re.IGNORECASE | re.DOTALL
)


class GenericRegexParser:
    def _normalize_date(self, day: str, month: str, year: str) -> str:
        """Convert date components to YYYY-MM-DD format."""
        year_int = int(year)
        if year_int < 100:
            year_int += 2000 if year_int < 50 else 1900
        return f"{year_int:04d}-{int(month):02d}-{int(day):02d}"

    def _extract_dates_from_section(self, text: str) -> list[str]:
        """Extract all dates from a text section."""
        dates = []

        # Try ISO format first (YYYY-MM-DD)
        for match in ISO_DATE_RE.finditer(text):
            year, month, day = match.groups()
            dates.append(f"{year}-{month}-{day}")

        # Try DD.MM.YYYY format
        for match in DATE_RE.finditer(text):
            day, month, year = match.groups()
            try:
                normalized = self._normalize_date(day, month, year)
                if normalized not in dates:  # Avoid duplicates
                    dates.append(normalized)
            except (ValueError, IndexError):
                continue

        return dates

    def parse(self, path: Path, raw_text: str) -> NormalizedProduct:
        product = NormalizedProduct()
        isin_match = ISIN_RE.search(raw_text)
        if isin_match:
            excerpt = truncate_excerpt(isin_match.group(0))
            product.isin = make_field(isin_match.group(0), 0.7, "pdf_regex", excerpt)

        valor_match = VALOR_RE.search(raw_text)
        if valor_match:
            excerpt = truncate_excerpt(valor_match.group(0))
            product.valor_number = make_field(valor_match.group(0), 0.4, "pdf_regex", excerpt)

        currency_match = CURRENCY_RE.search(raw_text)
        if currency_match:
            excerpt = truncate_excerpt(currency_match.group(0))
            product.currency = make_field(currency_match.group(0), 0.5, "pdf_regex", excerpt)

        ytm_match = YTM_RE.search(raw_text)
        if ytm_match:
            value = float(ytm_match.group(2).replace(",", "."))
            excerpt = truncate_excerpt(ytm_match.group(0))
            product.yield_to_maturity_pct_pa = make_field(value, 0.6, "pdf_regex", excerpt)

        wty_match = WTY_RE.search(raw_text)
        if wty_match:
            value = float(wty_match.group(2).replace(",", "."))
            excerpt = truncate_excerpt(wty_match.group(0))
            product.worst_to_yield_pct_pa = make_field(value, 0.6, "pdf_regex", excerpt)

        # Extract early redemption / observation dates
        obs_section_match = OBSERVATION_SECTION_RE.search(raw_text)
        if obs_section_match:
            section_text = obs_section_match.group(2)
            dates = self._extract_dates_from_section(section_text)

            if dates:
                # Store as observation dates (for autocall/early redemption)
                product.call_observation_dates = [
                    make_field(date, 0.7, "pdf_regex", truncate_excerpt(section_text[:100]))
                    for date in dates
                ]

        product.source_file_name = make_field(path.name if path else None, 1.0, "pdf")
        return product
