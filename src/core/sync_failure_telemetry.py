from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(slots=True)
class WriteFailureDetail:
    category: str
    error_type: str
    message: str
    failed_count: int = 0
    retryable: bool = False
    form_name: str = ""
    table_name: str = ""
    record_keys: list[str] = field(default_factory=list)


def build_record_keys(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    keys: list[str] = []
    for row in rows:
        normalized = {str(key).upper(): value for key, value in row.items()}
        parts: list[str] = []
        if normalized.get("FID") not in (None, ""):
            parts.append(f"FID={normalized['FID']}")
        if normalized.get("FBILLNO") not in (None, ""):
            parts.append(f"FBILLNO={normalized['FBILLNO']}")
        if not parts:
            for key in ("FNUMBER", "FENTRYID", "ID"):
                value = normalized.get(key)
                if value not in (None, ""):
                    parts.append(f"{key}={value}")
                    break
        if parts:
            keys.append("|".join(parts))
    return keys


def classify_failure(
    *,
    form_name: str,
    table_name: str,
    error_type: str,
    message: str,
    failed_rows: Iterable[Mapping[str, Any]] | None = None,
) -> WriteFailureDetail:
    normalized_type = (error_type or "").lower()
    normalized_message = (message or "").lower()

    category = "sql_error"
    retryable = False
    if "truncated" in normalized_message or "too long" in normalized_message:
        category = "string_truncation"
    elif "timeout" in normalized_message or "deadlock" in normalized_message:
        category = "transient_sql_error"
        retryable = True
    elif "session" in normalized_message or "login" in normalized_message or "auth" in normalized_message:
        category = "session_error"
        retryable = True
    elif "connection" in normalized_message or "operationalerror" in normalized_type:
        category = "connection_error"
        retryable = True

    failed_row_list = list(failed_rows or [])
    failed_count = len(failed_row_list) or 1
    return WriteFailureDetail(
        category=category,
        error_type=error_type,
        message=message,
        failed_count=failed_count,
        retryable=retryable,
        form_name=form_name,
        table_name=table_name,
        record_keys=build_record_keys(failed_row_list),
    )


def summarize_failure_details(details: Iterable[WriteFailureDetail]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for detail in details:
        summary[detail.category] = summary.get(detail.category, 0) + max(0, int(detail.failed_count or 0))
    return summary
