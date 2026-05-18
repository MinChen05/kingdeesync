from __future__ import annotations

from typing import Any


class FieldMappingResolver:
    def __init__(self, mappings: dict[str, dict[str, dict[str, Any]]] | None) -> None:
        self._mappings = mappings or {}

    def get_rule(self, table: str, field: str) -> dict[str, Any] | None:
        return self._mappings.get(table, {}).get(field)

    def resolve_field(self, table: str, field: str, row: dict[str, Any]) -> Any:
        rule = self.get_rule(table, field)
        if rule is None:
            return row.get(field)

        value = self._resolve_source_value(rule, row)
        if value is None or value == "":
            return rule.get("default")

        return self._coerce_value(table, field, value, rule)

    def _resolve_source_value(self, rule: dict[str, Any], row: dict[str, Any]) -> Any:
        for source in rule.get("sources", []):
            value = row.get(source)
            if value is None or value == "":
                continue
            return value
        return None

    def _coerce_value(self, table: str, field: str, value: Any, rule: dict[str, Any]) -> Any:
        value_type = str(rule.get("type", "string")).strip().lower()
        default = rule.get("default")

        if value_type == "decimal":
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        if value_type == "int":
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        if value_type == "string":
            return self._normalize_string(table, field, str(value), rule)

        return value

    def _normalize_string(self, table: str, field: str, value: str, rule: dict[str, Any]) -> str:
        max_length = rule.get("max_length")
        if not isinstance(max_length, int) or len(value) <= max_length:
            return value

        policy = str(rule.get("truncate_policy", "reject")).strip().lower()
        if policy == "trim":
            return value[:max_length]
        if policy == "reject":
            raise ValueError(f"{table}.{field} exceeds max_length={max_length}")
        return value
