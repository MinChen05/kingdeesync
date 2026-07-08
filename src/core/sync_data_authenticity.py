from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class FieldComparison:
    matched: bool
    db_value: str
    api_value: str


def normalize_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def compare_string(db_value: Any, api_value: Any) -> FieldComparison:
    db_text = normalize_text(db_value)
    api_text = normalize_text(api_value)
    return FieldComparison(db_text == api_text, db_text, api_text)


def _to_decimal(value: Any) -> Decimal | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def compare_decimal(
    db_value: Any,
    api_value: Any,
    tolerance: Decimal = Decimal("0.000001"),
) -> FieldComparison:
    db_dec = _to_decimal(db_value)
    api_dec = _to_decimal(api_value)
    db_text = normalize_text(db_value)
    api_text = normalize_text(api_value)
    if db_dec is None or api_dec is None:
        return FieldComparison(db_text == api_text, db_text, api_text)
    return FieldComparison(abs(db_dec - api_dec) <= tolerance, db_text, api_text)


def _to_datetime(value: Any) -> datetime | None:
    text = normalize_text(value).replace("T", " ")
    if not text:
        return None

    candidates = []
    if "." in text:
        candidates.append((text[:26], "%Y-%m-%d %H:%M:%S.%f"))
    candidates.extend(
        [
            (text[:19], "%Y-%m-%d %H:%M:%S"),
            (text[:10], "%Y-%m-%d"),
        ]
    )

    for candidate, fmt in candidates:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def compare_date(db_value: Any, api_value: Any) -> FieldComparison:
    db_dt = _to_datetime(db_value)
    api_dt = _to_datetime(api_value)
    db_text = normalize_text(db_value)
    api_text = normalize_text(api_value)
    if db_dt is None or api_dt is None:
        return FieldComparison(db_text == api_text, db_text, api_text)
    return FieldComparison(
        db_dt.replace(microsecond=0) == api_dt.replace(microsecond=0),
        db_text,
        api_text,
    )
