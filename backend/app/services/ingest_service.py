from __future__ import annotations

import json
import shutil
from pathlib import Path

from backend.app.db import models
from backend.app.settings import settings
from core.models import NormalizedProduct, make_field
from core.sources.pdf_termsheet import extract_text, parse_pdf
from core.utils.hashing import sha256_file


def _ensure_dirs() -> None:
    settings.output_dir.joinpath("parsed").mkdir(parents=True, exist_ok=True)
    settings.not_reviewed_dir.mkdir(parents=True, exist_ok=True)


def _derive_fx_risk(product: NormalizedProduct) -> bool | None:
    currency = product.currency.value if product.currency else None
    if currency and currency != "CHF":
        return True
    for underlying in product.underlyings:
        if underlying.reference_currency.value == "USD":
            return True
    return False


def process_pdf(path: Path) -> str:
    _ensure_dirs()
    file_hash = sha256_file(path)
    raw_text = extract_text(path)
    parsed = parse_pdf(path, raw_text)

    parsed.source_file_name = make_field(path.name, 1.0, "pdf")
    parsed.source_file_hash_sha256 = make_field(file_hash, 1.0, "pdf")
    parsed.parse_version = make_field("0.1", 1.0, "system")
    parsed.parse_confidence = make_field(0.4, 0.4, "system")

    fx_risk = _derive_fx_risk(parsed)
    if fx_risk is not None:
        parsed.fx_risk_flag = make_field(fx_risk, 0.6, "derived")

    output_path = settings.output_dir / "parsed" / f"{file_hash}.json"
    output_path.write_text(json.dumps(parsed.model_dump(), indent=2))

    dest = settings.not_reviewed_dir / path.name
    if dest.exists():
        dest = settings.not_reviewed_dir / f"{file_hash}-{path.name}"
    shutil.move(str(path), dest)

    product_id = models.upsert_product(
        normalized=parsed.model_dump(),
        raw_text=raw_text,
        source_kind="pdf",
        source_file_path=str(dest),
        source_file_hash_sha256=file_hash,
    )
    return product_id


def ingest_directory() -> list[str]:
    _ensure_dirs()
    ids: list[str] = []
    for path in settings.input_dir.glob("*.pdf"):
        ids.append(process_pdf(path))
    return ids
