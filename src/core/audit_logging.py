"""Structured audit log helpers for sync task lifecycle events."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, Enum):
        return value.value
    return str(value)


def emit_audit_log(
    logger: logging.Logger,
    scope: str,
    event: str,
    *,
    level: str = "info",
    **fields: Any,
) -> None:
    """Emit a single-line structured audit log entry."""
    payload = {"scope": scope, "event": event, **fields}
    message = f"[AUDIT] {json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default)}"
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)
