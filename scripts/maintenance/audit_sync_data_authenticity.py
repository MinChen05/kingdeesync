from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, ".")

from src.core.sync_data_authenticity import (  # noqa: E402
    AUDIT_SPECS,
    RowAuditResult,
    audit_row,
    detail_rows,
    load_targets_from_difference_csv,
    summarize_results,
)

Targets = dict[str, set[tuple[str, ...]]]
RowsByForm = dict[str, dict[tuple[str, ...], dict[str, object]]]
Fetcher = Callable[[Targets], RowsByForm]


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _empty_fetcher(_: Targets) -> RowsByForm:
    return {}


def run_audit(
    source: str | Path,
    forms: set[str],
    out_dir: str | Path,
    db_fetcher: Fetcher | None = None,
    api_fetcher: Fetcher | None = None,
) -> dict[str, object]:
    targets = load_targets_from_difference_csv(source, forms)
    db_rows = (db_fetcher or _empty_fetcher)(targets)
    api_rows = (api_fetcher or _empty_fetcher)(targets)

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
        [
            "form",
            "key",
            "status",
            "eligible_for_rehydration",
            "field",
            "severity",
            "db_value",
            "api_value",
        ],
    )

    return {
        "total": len(results),
        "summary": summary_path,
        "detail": detail_path,
    }


def _parse_forms(raw: str) -> set[str]:
    return {form.strip() for form in raw.split(",") if form.strip()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="审计同步数据与金蝶源数据的一致性")
    parser.add_argument("--source", default="logs/all_sync_document_zero_vs_kingdee_detail.csv")
    parser.add_argument("--forms", default="采购入库单,采购订单")
    parser.add_argument("--mode", choices=("dry-run", "verify"), default="dry-run")
    parser.add_argument("--out-dir", default="logs/sync_data_authenticity")
    args = parser.parse_args(argv)

    result = run_audit(args.source, _parse_forms(args.forms), args.out_dir)
    print(f"{args.mode}: audited {result['total']} rows")
    print(f"summary: {result['summary']}")
    print(f"detail: {result['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
