from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
import csv
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


class AuditStatus(str, Enum):
    PASSED = "passed"
    WARNING_ONLY = "warning_only"
    DIMENSION_MISMATCH = "dimension_mismatch"
    VALUE_MISMATCH = "value_mismatch"
    MISSING_DB = "missing_db"
    MISSING_API = "missing_api"
    IDENTITY_MISMATCH = "identity_mismatch"


@dataclass(frozen=True)
class AuthenticityField:
    name: str
    db_field: str
    api_field: str
    field_type: str
    severity: str


@dataclass(frozen=True)
class AuthenticitySpec:
    form: str
    table: str
    db_identity: tuple[str, ...]
    api_identity: tuple[str, ...]
    fields: dict[str, AuthenticityField]


@dataclass(frozen=True)
class AuditDifference:
    field: str
    severity: str
    db_value: str
    api_value: str
    matched: bool


@dataclass(frozen=True)
class RowAuditResult:
    form: str
    key: tuple[str, ...]
    status: AuditStatus
    eligible_for_rehydration: bool
    differences: tuple[AuditDifference, ...]


def _field(
    name: str,
    db_field: str,
    api_field: str,
    field_type: str,
    severity: str,
) -> AuthenticityField:
    return AuthenticityField(name, db_field, api_field, field_type, severity)


AUDIT_SPECS: dict[str, AuthenticitySpec] = {
    "采购入库单": AuthenticitySpec(
        form="采购入库单",
        table="T_STK_INSTOCK",
        db_identity=("FID", "FENTRYID"),
        api_identity=("FID", "FInStockEntry_FENTRYID"),
        fields={
            "FBILLNO": _field("单号", "FBILLNO", "FBillNo", "string", "blocker"),
            "FSEQ": _field("分录", "FSEQ", "FInStockEntry_FSEQ", "decimal", "blocker"),
            "FMATERIALNUMBER": _field(
                "物料", "FMATERIALNUMBER", "FMaterialId.FNUMBER", "string", "blocker"
            ),
            "FSUPPLIERNAME": _field(
                "供应商", "FSUPPLIERNAME", "FSupplierId.FNAME", "string", "blocker"
            ),
            "FREALQTY": _field("实收数量", "FREALQTY", "FRealQty", "decimal", "blocker"),
            "FDATE": _field("日期", "FDATE", "FDate", "date", "warning"),
            "FDOCUMENTSTATUS": _field(
                "状态", "FDOCUMENTSTATUS", "FDocumentStatus", "string", "warning"
            ),
            "FModifyDate": _field("修改日期", "FModifyDate", "FModifyDate", "date", "warning"),
        },
    ),
    "采购订单": AuthenticitySpec(
        form="采购订单",
        table="T_PUR_POORDER",
        db_identity=("FID", "FENTRYID"),
        api_identity=("FID", "FPOOrderEntry_FENTRYID"),
        fields={
            "FBillNo": _field("单号", "FBillNo", "FBillNo", "string", "blocker"),
            "FNUMBER": _field("物料", "FNUMBER", "FMaterialId.FNUMBER", "string", "blocker"),
            "FSupplier": _field("供应商", "FSupplier", "FSupplierId.FNAME", "string", "blocker"),
            "FQTY": _field("数量", "FQTY", "FQTY", "decimal", "blocker"),
            "FDocumentStatus": _field(
                "状态", "FDocumentStatus", "FDocumentStatus", "string", "warning"
            ),
            "FCreateDate": _field("创建日期", "FCreateDate", "FCreateDate", "date", "warning"),
            "FModifyDate": _field("修改日期", "FModifyDate", "FModifyDate", "date", "warning"),
            "FApproveDate": _field("审核日期", "FApproveDate", "FApproveDate", "date", "warning"),
        },
    ),
}


def _get_value(row: dict[str, Any], field: str) -> Any:
    if field in row:
        return row[field]
    field_lower = field.lower()
    for key, value in row.items():
        if key.lower() == field_lower:
            return value
    return None


def _row_key(row: dict[str, Any] | None, identity: tuple[str, ...]) -> tuple[str, ...]:
    if row is None:
        return tuple()
    return tuple(normalize_text(_get_value(row, field)) for field in identity)


def _compare(field: AuthenticityField, db_row: dict[str, Any], api_row: dict[str, Any]) -> FieldComparison:
    db_value = _get_value(db_row, field.db_field)
    api_value = _get_value(api_row, field.api_field)
    if field.field_type == "decimal":
        return compare_decimal(db_value, api_value)
    if field.field_type == "date":
        return compare_date(db_value, api_value)
    return compare_string(db_value, api_value)


def audit_row(
    spec: AuthenticitySpec,
    db_row: dict[str, Any] | None,
    api_row: dict[str, Any] | None,
) -> RowAuditResult:
    if db_row is None:
        key = _row_key(api_row, spec.api_identity)
        return RowAuditResult(spec.form, key, AuditStatus.MISSING_DB, False, tuple())
    if api_row is None:
        key = _row_key(db_row, spec.db_identity)
        return RowAuditResult(spec.form, key, AuditStatus.MISSING_API, False, tuple())

    db_key = _row_key(db_row, spec.db_identity)
    api_key = _row_key(api_row, spec.api_identity)
    if db_key != api_key:
        differences = tuple(
            AuditDifference(field, "blocker", db_value, api_value, False)
            for field, db_value, api_value in zip(spec.db_identity, db_key, api_key)
            if db_value != api_value
        )
        return RowAuditResult(spec.form, db_key, AuditStatus.IDENTITY_MISMATCH, False, differences)

    differences: list[AuditDifference] = []
    for field_key, field in spec.fields.items():
        comparison = _compare(field, db_row, api_row)
        if not comparison.matched:
            differences.append(
                AuditDifference(
                    field=field_key,
                    severity=field.severity,
                    db_value=comparison.db_value,
                    api_value=comparison.api_value,
                    matched=False,
                )
            )

    blocker_fields = {diff.field for diff in differences if diff.severity == "blocker"}
    warning_only = bool(differences) and not blocker_fields
    if not differences:
        status = AuditStatus.PASSED
        eligible = True
    elif warning_only:
        status = AuditStatus.WARNING_ONLY
        eligible = True
    elif blocker_fields <= {"FREALQTY", "FQTY"}:
        status = AuditStatus.VALUE_MISMATCH
        eligible = True
    else:
        status = AuditStatus.DIMENSION_MISMATCH
        eligible = False

    return RowAuditResult(spec.form, db_key, status, eligible, tuple(differences))


def load_targets_from_difference_csv(
    path: str | Path,
    forms: set[str],
) -> dict[str, set[tuple[str, ...]]]:
    targets: dict[str, set[tuple[str, ...]]] = {form: set() for form in forms}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            form = normalize_text(row.get("form"))
            if form not in forms:
                continue
            key_text = normalize_text(row.get("db_key") or row.get("key"))
            if not key_text:
                continue
            targets.setdefault(form, set()).add(tuple(part.strip() for part in key_text.split("|")))
    return {form: keys for form, keys in targets.items() if keys}


def summarize_results(results: list[RowAuditResult]) -> list[dict[str, str | int]]:
    counts: dict[AuditStatus, int] = {status: 0 for status in AuditStatus}
    eligible_counts: dict[AuditStatus, int] = {status: 0 for status in AuditStatus}
    for result in results:
        counts[result.status] += 1
        if result.eligible_for_rehydration:
            eligible_counts[result.status] += 1

    rows: list[dict[str, str | int]] = []
    for status in AuditStatus:
        if counts[status] == 0:
            continue
        rows.append(
            {
                "status": status.value,
                "count": counts[status],
                "eligible_for_rehydration": eligible_counts[status],
            }
        )
    return rows


def detail_rows(results: list[RowAuditResult]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for result in results:
        key = "|".join(result.key)
        base = {
            "form": result.form,
            "key": key,
            "status": result.status.value,
            "eligible_for_rehydration": "true" if result.eligible_for_rehydration else "false",
        }
        if not result.differences:
            rows.append(
                {
                    **base,
                    "field": "",
                    "severity": "",
                    "db_value": "",
                    "api_value": "",
                }
            )
            continue
        for diff in result.differences:
            rows.append(
                {
                    **base,
                    "field": diff.field,
                    "severity": diff.severity,
                    "db_value": diff.db_value,
                    "api_value": diff.api_value,
                }
            )
    return rows
