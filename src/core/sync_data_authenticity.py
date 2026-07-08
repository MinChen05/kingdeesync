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


BLOCKER_STATUSES = {
    AuditStatus.MISSING_DB,
    AuditStatus.MISSING_API,
    AuditStatus.IDENTITY_MISMATCH,
    AuditStatus.DIMENSION_MISMATCH,
    AuditStatus.VALUE_MISMATCH,
}


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
    identity_confirmed: bool = True
    identity_kind: str = "entry"
    batch: str = "business_documents"
    unsupported_reason: str | None = None


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


FORM_BATCHES = {
    "business_documents": (
        "销售订单",
        "销售出库单",
        "销售退货单",
        "发货通知单",
        "采购订单",
        "采购入库单",
        "委外订单",
        "应付单",
        "应收单",
    ),
    "production_documents": (
        "生产入库单",
        "生产订单主表",
        "生产订单明细",
        "生产用料清单主表",
        "生产用料清单明细表",
        "预测订单",
    ),
    "snapshot_master_data": (
        "即时库存",
        "客户资料",
        "物料",
        "仓库",
        "物料清单",
        "物料清单子项",
    ),
}

UNSUPPORTED_FORMS = {
    "科目余额表": "report_form_requires_separate_design",
}


AUDIT_SPECS: dict[str, AuthenticitySpec] = {
    "采购入库单": AuthenticitySpec(
        form="采购入库单",
        table="STK_InStock",
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
        table="PUR_PurchaseOrder",
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


def _csv_join(values: list[str] | set[str] | tuple[str, ...]) -> str:
    return ",".join(sorted({value for value in values if value}, key=str.casefold))


def _split_field_keys(field_keys: Any) -> set[str]:
    if not field_keys:
        return set()
    if isinstance(field_keys, str):
        return {field.strip() for field in field_keys.split(",") if field.strip()}
    return {normalize_text(field) for field in field_keys if normalize_text(field)}


def _missing_fields(required_fields: set[str], available_fields: set[str]) -> str:
    available_lower = {field.casefold() for field in available_fields}
    missing = {field for field in required_fields if field.casefold() not in available_lower}
    return _csv_join(missing)


def _batch_for_form(form: str) -> str:
    for batch, forms in FORM_BATCHES.items():
        if form in forms:
            return batch
    return ""


def build_mapping_draft_rows(
    form_queries: dict[str, dict[str, Any]],
    tables: dict[str, dict[str, Any]],
    db_columns: dict[str, set[str]],
    audit_specs: dict[str, AuthenticitySpec] = AUDIT_SPECS,
) -> list[dict[str, str]]:
    forms = list(dict.fromkeys([*form_queries.keys(), *tables.keys(), *audit_specs.keys()]))
    rows: list[dict[str, str]] = []

    for form in forms:
        query = form_queries.get(form, {})
        table_config = tables.get(form, {})
        spec = audit_specs.get(form)
        table = normalize_text(table_config.get("table") or (spec.table if spec else ""))
        form_id = normalize_text(query.get("FormId"))
        api_field_keys = _split_field_keys(query.get("FieldKeys"))
        table_db_columns = {normalize_text(column) for column in db_columns.get(table, set())}
        db_columns_available = table in db_columns
        unsupported_reason = UNSUPPORTED_FORMS.get(form) or (spec.unsupported_reason if spec else None)

        db_identity = spec.db_identity if spec else tuple()
        api_identity = spec.api_identity if spec else tuple()
        fields = spec.fields if spec else {}
        required_db_fields = {*db_identity, *(field.db_field for field in fields.values())}
        required_api_fields = {*api_identity, *(field.api_field for field in fields.values())}
        blocker_fields = {key for key, field in fields.items() if field.severity == "blocker"}
        warning_fields = {key for key, field in fields.items() if field.severity == "warning"}

        rows.append(
            {
                "form": form,
                "table": table,
                "form_id": form_id,
                "batch": spec.batch if spec else _batch_for_form(form),
                "identity_kind": spec.identity_kind if spec else ("report" if unsupported_reason else ""),
                "identity_confirmed": "true" if spec and spec.identity_confirmed else "false",
                "db_identity": _csv_join(db_identity),
                "api_identity": _csv_join(api_identity),
                "blocker_fields": _csv_join(blocker_fields),
                "warning_fields": _csv_join(warning_fields),
                "api_field_keys": _csv_join(api_field_keys),
                "db_columns": _csv_join(table_db_columns),
                "missing_db_fields": _missing_fields(required_db_fields, table_db_columns),
                "missing_api_fields": _missing_fields(required_api_fields, api_field_keys),
                "unsupported_reason": unsupported_reason or "",
                "db_columns_available": "true" if db_columns_available else "false",
            }
        )

    return rows


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


def blocker_rows(results: list[RowAuditResult]) -> list[dict[str, str]]:
    return detail_rows([result for result in results if result.status in BLOCKER_STATUSES])
