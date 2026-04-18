#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare Python and .NET query results for the same batch."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.config_manager import config_manager  # noqa: E402
from src.core.kingdee_api import kingdee_client  # noqa: E402


def parse_forms(raw: str) -> List[str]:
    return [x.strip() for x in raw.replace(";", ",").replace("|", ",").split(",") if x.strip()]


def normalize_value(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, float):
        return format(value, ".15g")

    if isinstance(value, dict):
        items = [
            f"{k}:{normalize_value(v)}"
            for k, v in sorted(value.items(), key=lambda kv: kv[0].lower())
        ]
        return "{" + ",".join(items) + "}"

    if isinstance(value, (list, tuple)):
        return "[" + ",".join(normalize_value(x) for x in value) + "]"

    return str(value)


def canonicalize_row(row: Dict[str, Any]) -> str:
    pairs = [
        f"{k}={normalize_value(v)}"
        for k, v in sorted(row.items(), key=lambda kv: kv[0].lower())
    ]
    return "|".join(pairs)


def sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def summarize_rows(form_name: str, form_id: str, rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    canonical_rows = sorted(canonicalize_row(row) for row in rows)
    payload = "\n".join(canonical_rows)
    row_hash = sha256_hex(payload)
    sample = [sha256_hex(x) for x in canonical_rows[:3]]
    return {
        "formName": form_name,
        "formId": form_id,
        "rowCount": len(canonical_rows),
        "rowHash": row_hash,
        "sampleRowHashes": sample,
    }


def query_python_batch(forms: List[str], start_row: int, limit: int) -> Dict[str, Dict[str, Any]]:
    if not kingdee_client.test_connection():
        raise RuntimeError("Python client failed to authenticate with Kingdee API")

    queries = config_manager.get_form_queries()
    result: Dict[str, Dict[str, Any]] = {}

    for form in forms:
        template = queries.get(form)
        if not isinstance(template, dict):
            result[form] = {
                "formName": form,
                "formId": form,
                "rowCount": 0,
                "rowHash": "",
                "sampleRowHashes": [],
                "error": "form query template not found",
            }
            continue

        params = copy.deepcopy(template)
        params["StartRow"] = start_row
        params["Limit"] = limit

        rows = kingdee_client.query_data(form, params)
        if rows is None:
            rows = []

        form_id = str(template.get("FormId") or form)
        result[form] = summarize_rows(form, form_id, rows)

    return result


def run_dotnet_parity(
    forms: List[str],
    mode: str,
    start_row: int,
    limit: int,
    config_path: str,
    project_path: str,
) -> Tuple[int, str, str, Dict[str, Any]]:
    with subprocess.Popen(
        [
            "dotnet",
            "run",
            "--project",
            project_path,
            "--",
            "parity",
            "--config",
            config_path,
            "--mode",
            mode,
            "--tables",
            ",".join(forms),
            "--start-row",
            str(start_row),
            "--limit",
            str(limit),
            "--output",
            os.path.join(PROJECT_ROOT, "logs", "dotnet-parity.json"),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    ) as proc:
        stdout, stderr = proc.communicate()
        exit_code = proc.returncode

    output_file = os.path.join(PROJECT_ROOT, "logs", "dotnet-parity.json")
    data: Dict[str, Any] = {}
    if exit_code == 0 and os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    return exit_code, stdout, stderr, data


def compare_results(forms: List[str], py_results: Dict[str, Dict[str, Any]], dotnet_results: Dict[str, Any]) -> Dict[str, Any]:
    dotnet_map = dotnet_results.get("results", {}) if isinstance(dotnet_results, dict) else {}

    comparisons: Dict[str, Any] = {}
    matched = 0
    for form in forms:
        py_item = py_results.get(form, {})
        dn_item = dotnet_map.get(form, {}) if isinstance(dotnet_map, dict) else {}

        if not py_item:
            comparisons[form] = {"status": "python_missing"}
            continue
        if not dn_item:
            comparisons[form] = {
                "status": "dotnet_missing",
                "python": py_item,
            }
            continue

        py_count = py_item.get("rowCount")
        dn_count = dn_item.get("rowCount")
        py_hash = py_item.get("rowHash")
        dn_hash = dn_item.get("rowHash")

        is_match = py_count == dn_count and py_hash == dn_hash
        if is_match:
            matched += 1

        comparisons[form] = {
            "status": "matched" if is_match else "mismatch",
            "pythonRowCount": py_count,
            "dotnetRowCount": dn_count,
            "pythonRowHash": py_hash,
            "dotnetRowHash": dn_hash,
        }

    return {
        "matched": matched,
        "total": len(forms),
        "byForm": comparisons,
    }


def default_config_path() -> str:
    return os.path.join(PROJECT_ROOT, "config.ini")


def default_dotnet_project() -> str:
    return os.path.join(PROJECT_ROOT, "dotnet", "src", "Kingdee.SyncTool.Cli", "Kingdee.SyncTool.Cli.csproj")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Python and .NET same-batch query summaries")
    parser.add_argument("--tables", required=False, default="", help="Comma-separated form names")
    parser.add_argument("--mode", default="full", choices=["incremental", "full", "complete", "reset"])
    parser.add_argument("--start-row", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--config", default=default_config_path())
    parser.add_argument("--dotnet-project", default=default_dotnet_project())
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "logs", "python-dotnet-parity.json"))
    parser.add_argument("--skip-dotnet", action="store_true", help="Only query Python side and skip dotnet command")
    args = parser.parse_args()

    forms = parse_forms(args.tables)
    if not forms:
        defaults = config_manager.get_sync_config().get("default_forms", [])
        if isinstance(defaults, list):
            forms = [str(x).strip() for x in defaults if str(x).strip()]

    if not forms:
        print("No forms provided. Use --tables or configure [SYNC].default_forms", file=sys.stderr)
        return 2

    py_results = query_python_batch(forms, args.start_row, args.limit)

    dotnet_exit_code = None
    dotnet_stdout = ""
    dotnet_stderr = ""
    dotnet_report: Dict[str, Any] = {}

    if not args.skip_dotnet:
        try:
            (
                dotnet_exit_code,
                dotnet_stdout,
                dotnet_stderr,
                dotnet_report,
            ) = run_dotnet_parity(
                forms=forms,
                mode=args.mode,
                start_row=args.start_row,
                limit=args.limit,
                config_path=args.config,
                project_path=args.dotnet_project,
            )
        except FileNotFoundError:
            dotnet_exit_code = 127
            dotnet_stderr = "dotnet command not found"

    comparison = compare_results(forms, py_results, dotnet_report)

    report = {
        "generatedAt": datetime.now().isoformat(),
        "mode": args.mode,
        "startRow": args.start_row,
        "limit": args.limit,
        "forms": forms,
        "python": {"results": py_results},
        "dotnet": {
            "exitCode": dotnet_exit_code,
            "stdout": dotnet_stdout,
            "stderr": dotnet_stderr,
            "report": dotnet_report,
        },
        "comparison": comparison,
    }

    output_path = args.output
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Forms compared: {comparison['matched']}/{comparison['total']} matched")
    print(f"Report saved: {output_path}")

    if args.skip_dotnet:
        return 0

    return 0 if comparison["matched"] == comparison["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
