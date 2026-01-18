from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models.fields import Field
from core.models.normalized import NormalizedProduct


@dataclass
class MergeDecision:
    field: str
    from_source: str
    to_source: str
    reason: str


def _field_value(value: Any) -> Any:
    if isinstance(value, Field):
        return value.value
    return value


def _field_source(value: Any) -> str:
    if isinstance(value, Field):
        return value.source
    return "unknown"


def merge_products(
    primary: NormalizedProduct,
    secondary: NormalizedProduct,
    prefer_secondary_fields: set[str] | None = None,
) -> NormalizedProduct:
    prefer_secondary_fields = prefer_secondary_fields or set()
    data = primary.model_copy(deep=True)
    audit_trail: list[dict[str, str]] = list(data.audit_trail)

    for field_name, primary_value in primary.model_dump().items():
        if field_name in {"audit_trail", "id"}:
            continue
        secondary_value = getattr(secondary, field_name)

        if isinstance(primary_value, list):
            if not primary_value and secondary_value:
                setattr(data, field_name, secondary_value)
            continue

        primary_field = getattr(primary, field_name)
        secondary_field = getattr(secondary, field_name)
        if not isinstance(primary_field, Field) or not isinstance(secondary_field, Field):
            continue

        if primary_field.value is None and secondary_field.value is not None:
            setattr(data, field_name, secondary_field)
            continue

        if primary_field.value is not None and secondary_field.value is not None:
            if field_name in prefer_secondary_fields and primary_field.value != secondary_field.value:
                setattr(data, field_name, secondary_field)
                audit_trail.append(
                    {
                        "field": field_name,
                        "from": _field_source(primary_field),
                        "to": _field_source(secondary_field),
                        "reason": "higher_confidence",
                    }
                )

    data.audit_trail = audit_trail
    return data
