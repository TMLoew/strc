from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator

T = TypeVar("T")


class Field(BaseModel, Generic[T]):
    value: Optional[T] = None
    confidence: float = 0.0
    source: str = "unknown"
    raw_excerpt: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value


def make_field(
    value: Optional[T] = None,
    confidence: float = 0.0,
    source: str = "unknown",
    raw_excerpt: Optional[str] = None,
) -> Field[T]:
    return Field(value=value, confidence=confidence, source=source, raw_excerpt=raw_excerpt)
