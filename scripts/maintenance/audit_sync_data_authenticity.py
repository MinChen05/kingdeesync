from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

sys.path.insert(0, ".")

from src.config.config_manager import config_manager  # noqa: E402
from src.core.sync_data_authenticity import (  # noqa: E402
    AUDIT_SPECS,
    FORM_BATCHES,
    AuthenticitySpec,
    RowAuditResult,
    audit_row,
    blocker_rows,
    build_mapping_draft_rows,
    detail_rows,
    load_targets_from_difference_csv,
    normalize_text,
    summarize_results,
)

Targets = dict[str, set[tuple[str, ...]]]
RowsByForm = dict[str, dict[tuple[str, ...], dict[str, object]]]
Fetcher = Callable[[Targets], RowsByForm]

DISCOVERY_FIELDNAMES = [
    "form",
    "table",
    "form_id",
    "batch",
    "identity_kind",
    "identity_confirmed",
    "db_identity",
    "api_identity",
    "blocker_fields",
    "warning_fields",
    "api_field_keys",
    "db_columns",
    "missing_db_fields",
    "missing_api_fields",
    "unsupported_reason",
    "db_columns_available",
]

DETAIL_FIELDNAMES = [
    "form",
    "key",
    "status",
    "eligible_for_rehydration",
    "field",
    "severity",
    "db_value",
    "api_value",
]


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _empty_fetcher(_: Targets) -> RowsByForm:
    return {}


def _quote_identifier(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


def _ordered_keys(keys: Iterable[tuple[str, ...]]) -> list[tuple[str, ...]]:
    return sorted(keys, key=lambda item: tuple(str(part) for part in item))


def build_db_query(
    spec: AuthenticitySpec,
    keys: set[tuple[str, ...]],
) -> tuple[str, list[str]]:
    if not keys:
        return "", []

    columns = list(dict.fromkeys([*spec.db_identity, *(field.db_field for field in spec.fields.values())]))
    select_sql = ", ".join(_quote_identifier(column) for column in columns)
    identity_sql = " AND ".join(f"{_quote_identifier(column)} = ?" for column in spec.db_identity)
    where_parts = [f"({identity_sql})" for _ in keys]
    params: list[str] = []
    for key in _ordered_keys(keys):
        params.extend(str(part) for part in key)

    sql = f"SELECT {select_sql} FROM {_quote_identifier(spec.table)} WHERE {' OR '.join(where_parts)}"
    return sql, params


def iter_db_queries(
    spec: AuthenticitySpec,
    keys: set[tuple[str, ...]],
    max_params: int = 2000,
) -> Iterable[tuple[str, list[str]]]:
    identity_width = max(1, len(spec.db_identity))
    chunk_size = max(1, max_params // identity_width)
    ordered_keys = _ordered_keys(keys)
    for index in range(0, len(ordered_keys), chunk_size):
        yield build_db_query(spec, set(ordered_keys[index : index + chunk_size]))


def _execute_query(cursor, sql: str, params: list[str]) -> None:
    cursor.execute(sql, *params)


def _value_literal(value: str) -> str:
    text = normalize_text(value)
    if text.isdigit():
        return text
    return "'" + text.replace("'", "''") + "'"


def build_api_filter(
    spec: AuthenticitySpec,
    fids: set[str],
    base_filter: str | None = None,
) -> str:
    fid_values = ",".join(_value_literal(fid) for fid in sorted(fids))
    fid_filter = f"{spec.api_identity[0]} IN ({fid_values})"
    base = normalize_text(base_filter)
    if not base or base == "1=1":
        return fid_filter
    return f"({base}) AND {fid_filter}"


def _row_to_dict(cursor, row) -> dict[str, object]:
    if isinstance(row, dict):
        return dict(row)
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _identity_key(row: dict[str, object], identity: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(normalize_text(row.get(field)) for field in identity)


def fetch_db_rows(targets: Targets) -> RowsByForm:
    from src.core.mysql_manager import MySQLManager

    manager = MySQLManager()
    rows_by_form: RowsByForm = {}
    try:
        if not manager.connect():
            raise RuntimeError("数据库连接失败")
        for form, keys in targets.items():
            if not keys:
                continue
            spec = AUDIT_SPECS[form]
            form_rows: dict[tuple[str, ...], dict[str, object]] = {}
            for sql, params in iter_db_queries(spec, keys):
                _execute_query(manager.cursor, sql, params)
                for row in manager.cursor.fetchall() or []:
                    row_dict = _row_to_dict(manager.cursor, row)
                    form_rows[_identity_key(row_dict, spec.db_identity)] = row_dict
            rows_by_form[form] = form_rows
        return rows_by_form
    finally:
        manager.disconnect()


def fetch_api_rows(targets: Targets) -> RowsByForm:
    from src.core.kingdee_api import KingdeeAPIClient

    client = KingdeeAPIClient()
    rows_by_form: RowsByForm = {}
    try:
        if not client.ensure_session():
            raise RuntimeError("金蝶登录失败")
        form_queries = config_manager.get_form_queries()
        for form, keys in targets.items():
            if not keys:
                continue
            spec = AUDIT_SPECS[form]
            query_params = form_queries[form].copy()
            fids = {key[0] for key in keys}
            query_params["FilterString"] = build_api_filter(
                spec,
                fids,
                query_params.get("FilterString"),
            )
            rows = client.query_data(form, query_params) or []
            form_rows: dict[tuple[str, ...], dict[str, object]] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = _identity_key(row, spec.api_identity)
                if key in keys:
                    form_rows[key] = row
            rows_by_form[form] = form_rows
        return rows_by_form
    finally:
        client.logout()


def _column_value(row: object, cursor, name: str, index: int) -> str:
    if isinstance(row, dict):
        return normalize_text(row.get(name))
    if hasattr(row, name):
        return normalize_text(getattr(row, name))
    try:
        return normalize_text(row[index])  # type: ignore[index]
    except (IndexError, TypeError):
        columns = [column[0] for column in cursor.description]
        row_dict = dict(zip(columns, row))  # type: ignore[arg-type]
        return normalize_text(row_dict.get(name))


def fetch_db_columns() -> dict[str, set[str]]:
    from src.core.mysql_manager import MySQLManager

    sql = """
    SELECT TABLE_NAME, COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    manager = MySQLManager()
    columns_by_table: dict[str, set[str]] = {}
    try:
        if not manager.connect():
            raise RuntimeError("数据库连接失败")
        manager.cursor.execute(sql)
        for row in manager.cursor.fetchall() or []:
            table = _column_value(row, manager.cursor, "TABLE_NAME", 0)
            column = _column_value(row, manager.cursor, "COLUMN_NAME", 1)
            if table and column:
                columns_by_table.setdefault(table, set()).add(column)
        return columns_by_table
    finally:
        manager.disconnect()


def _table_entries_from_config() -> dict[str, dict[str, str]]:
    table_mapping = config_manager.get_table_mapping()
    insert_methods = config_manager.get_insert_method_map()
    return {
        form: {
            "table": table,
            "insert_method": insert_methods.get(form, ""),
        }
        for form, table in table_mapping.items()
    }


def run_discovery(
    out_dir: str | Path,
    form_queries: dict[str, dict[str, Any]] | None = None,
    tables: dict[str, dict[str, Any]] | None = None,
    db_columns: dict[str, set[str]] | None = None,
) -> dict[str, object]:
    discovered_form_queries = form_queries if form_queries is not None else config_manager.get_form_queries()
    discovered_tables = tables if tables is not None else _table_entries_from_config()
    discovered_db_columns = db_columns if db_columns is not None else fetch_db_columns()

    rows = build_mapping_draft_rows(
        discovered_form_queries,
        discovered_tables,
        discovered_db_columns,
    )
    configured_forms = set(discovered_form_queries) | set(discovered_tables)
    if configured_forms:
        rows = [row for row in rows if row.get("form") in configured_forms]
    output_dir = Path(out_dir)
    mapping_path = output_dir / "authenticity_mapping_draft.csv"
    _write_csv(mapping_path, rows, DISCOVERY_FIELDNAMES)
    return {
        "rows": len(rows),
        "mapping_draft": mapping_path,
    }


def run_audit(
    source: str | Path,
    forms: set[str],
    out_dir: str | Path,
    db_fetcher: Fetcher | None = None,
    api_fetcher: Fetcher | None = None,
    write_blockers: bool = False,
) -> dict[str, object]:
    targets = load_targets_from_difference_csv(source, forms)
    db_rows = (db_fetcher or fetch_db_rows)(targets)
    api_rows = (api_fetcher or fetch_api_rows)(targets)

    results: list[RowAuditResult] = []
    for form, keys in targets.items():
        spec = AUDIT_SPECS[form]
        form_db_rows = db_rows.get(form, {})
        form_api_rows = api_rows.get(form, {})
        for key in sorted(keys):
            results.append(audit_row(spec, form_db_rows.get(key), form_api_rows.get(key)))

    output_dir = Path(out_dir)
    summary_path = output_dir / "sync_data_authenticity_summary.csv"
    detail_path = output_dir / "sync_data_authenticity_detail.csv"
    _write_csv(
        summary_path,
        summarize_results(results),
        ["status", "count", "eligible_for_rehydration"],
    )
    _write_csv(
        detail_path,
        detail_rows(results),
        DETAIL_FIELDNAMES,
    )

    report: dict[str, object] = {
        "total": len(results),
        "summary": summary_path,
        "detail": detail_path,
    }
    if write_blockers:
        blockers_path = output_dir / "sync_data_authenticity_blockers.csv"
        _write_csv(blockers_path, blocker_rows(results), DETAIL_FIELDNAMES)
        report["blockers"] = blockers_path
    return report


def _parse_forms(raw: str) -> set[str]:
    return {form.strip() for form in raw.split(",") if form.strip()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="审计同步数据与金蝶源数据的一致性")
    parser.add_argument("--source", default="logs/all_sync_document_zero_vs_kingdee_detail.csv")
    parser.add_argument("--forms", default=None)
    parser.add_argument("--batch", choices=tuple(FORM_BATCHES))
    parser.add_argument("--mode", choices=("dry-run", "verify"), default="dry-run")
    parser.add_argument("--out-dir", default="logs/sync_data_authenticity")
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args(argv)

    if args.discover:
        result = run_discovery(args.out_dir)
        print(f"discovery: wrote {result['mapping_draft']}")
        return 0

    if args.forms:
        forms = _parse_forms(args.forms)
    elif args.batch:
        forms = set(FORM_BATCHES[args.batch])
    else:
        forms = _parse_forms("采购入库单,采购订单")

    result = run_audit(args.source, forms, args.out_dir, write_blockers=True)
    print(f"{args.mode}: audited {result['total']} rows")
    print(f"summary: {result['summary']}")
    print(f"detail: {result['detail']}")
    if "blockers" in result:
        print(f"blockers: {result['blockers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
