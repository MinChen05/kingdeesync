---
change: verify-sync-data-authenticity
design-doc: docs/superpowers/specs/2026-07-08-sync-data-authenticity-design.md
base-ref: 7642b2b4dcf1b7cf02a50286dcb2cfcad0fd7849
---

# Sync Data Authenticity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable authenticity audit gate for purchase instock and purchase order rehydration.

**Architecture:** Add an isolated core audit module with declarative form specs, field comparators, row classification, and CSV report writing. Add a maintenance script that reads target identities from the existing difference CSV, queries current DB/API rows, and writes dry-run or verify reports without directly mutating data.

**Tech Stack:** Python standard library, existing `MySQLManager`, existing `KingdeeAPIClient`, pytest.

---

## File Structure

- Create `src/core/sync_data_authenticity.py`: data classes, field comparators, purchase specs, row auditor, report writer.
- Create `scripts/maintenance/audit_sync_data_authenticity.py`: CLI wrapper for dry-run and verify reports.
- Create `tests/test_sync_data_authenticity.py`: unit tests for comparators, specs, row classification, and report rows.
- Create `tests/test_audit_sync_data_authenticity_script.py`: script-level tests with mocked DB/API loading functions.
- Modify `openspec/changes/verify-sync-data-authenticity/tasks.md`: mark tasks as implementation completes.

### Task 1: Core Types And Comparators

**Files:**
- Create: `src/core/sync_data_authenticity.py`
- Test: `tests/test_sync_data_authenticity.py`

- [ ] **Step 1: Write failing comparator tests**

Add tests:

```python
from src.core.sync_data_authenticity import compare_decimal, compare_string, compare_date


def test_compare_decimal_accepts_equivalent_scale():
    assert compare_decimal("12.500000", "12.5").matched is True


def test_compare_decimal_reports_difference():
    result = compare_decimal("0", "1872000.0000000000")
    assert result.matched is False
    assert result.db_value == "0"
    assert result.api_value == "1872000.0000000000"


def test_compare_string_trims_spaces():
    assert compare_string(" MAT-001 ", "MAT-001").matched is True


def test_compare_date_compares_to_seconds():
    assert compare_date("2026-07-08 10:20:07.833333", "2026-07-08T10:20:07.833").matched is True
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

Expected: import failure for `src.core.sync_data_authenticity`.

- [ ] **Step 3: Implement comparator primitives**

Create `src/core/sync_data_authenticity.py` with:

```python
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


def _decimal_text(value: Any) -> str:
    return normalize_text(value)


def _to_decimal(value: Any) -> Decimal | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def compare_decimal(db_value: Any, api_value: Any, tolerance: Decimal = Decimal("0.000001")) -> FieldComparison:
    db_dec = _to_decimal(db_value)
    api_dec = _to_decimal(api_value)
    db_text = _decimal_text(db_value)
    api_text = _decimal_text(api_value)
    if db_dec is None or api_dec is None:
        return FieldComparison(db_text == api_text, db_text, api_text)
    return FieldComparison(abs(db_dec - api_dec) <= tolerance, db_text, api_text)


def _to_datetime(value: Any) -> datetime | None:
    text = normalize_text(value).replace("T", " ")
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:26] if "%f" in fmt else text[:19 if "%S" in fmt else 10], fmt)
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
    return FieldComparison(db_dt.replace(microsecond=0) == api_dt.replace(microsecond=0), db_text, api_text)
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

Expected: comparator tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/sync_data_authenticity.py tests/test_sync_data_authenticity.py
git commit -m "feat: add sync authenticity comparators"
```

### Task 2: Form Specs And Row Classification

**Files:**
- Modify: `src/core/sync_data_authenticity.py`
- Modify: `tests/test_sync_data_authenticity.py`

- [ ] **Step 1: Add failing spec/classification tests**

Add tests:

```python
from src.core.sync_data_authenticity import AUDIT_SPECS, AuditStatus, audit_row


def test_purchase_instock_spec_marks_date_as_warning():
    spec = AUDIT_SPECS["采购入库单"]
    assert spec.fields["FDATE"].severity == "warning"
    assert spec.fields["FREALQTY"].severity == "blocker"


def test_audit_row_blocks_on_material_mismatch():
    spec = AUDIT_SPECS["采购入库单"]
    db_row = {"FID": 1, "FENTRYID": 2, "FBILLNO": "RK1", "FSEQ": 1, "FMATERIALNUMBER": "A", "FSUPPLIERNAME": "S", "FREALQTY": "10"}
    api_row = {"FID": 1, "FInStockEntry_FENTRYID": 2, "FBillNo": "RK1", "FInStockEntry_FSEQ": 1, "FMaterialId.FNUMBER": "B", "FSupplierId.FNAME": "S", "FRealQty": "10"}
    result = audit_row(spec, db_row, api_row)
    assert result.status == AuditStatus.DIMENSION_MISMATCH
    assert result.eligible_for_rehydration is False


def test_audit_row_allows_warning_only_date_mismatch():
    spec = AUDIT_SPECS["采购订单"]
    db_row = {"FID": 1, "FENTRYID": 2, "FBillNo": "PO1", "FNUMBER": "A", "FSupplier": "S", "FQTY": "10", "FModifyDate": "2026-07-01 00:00:00"}
    api_row = {"FID": 1, "FPOOrderEntry_FENTRYID": 2, "FBillNo": "PO1", "FMaterialId.FNUMBER": "A", "FSupplierId.FNAME": "S", "FQTY": "10", "FModifyDate": "2026-07-02 00:00:00"}
    result = audit_row(spec, db_row, api_row)
    assert result.status == AuditStatus.WARNING_ONLY
    assert result.eligible_for_rehydration is True
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

Expected: missing `AUDIT_SPECS`, `AuditStatus`, and `audit_row`.

- [ ] **Step 3: Implement specs and row classification**

Add data classes:

```python
from enum import Enum


class AuditStatus(str, Enum):
    PASSED = "passed"
    WARNING_ONLY = "warning_only"
    DIMENSION_MISMATCH = "dimension_mismatch"
    VALUE_MISMATCH = "value_mismatch"
    MISSING_DB = "missing_db"
    MISSING_API = "missing_api"


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
```

Implement `AUDIT_SPECS` for `采购入库单` and `采购订单`, plus `audit_row()`.

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/sync_data_authenticity.py tests/test_sync_data_authenticity.py
git commit -m "feat: classify sync authenticity rows"
```

### Task 3: Report Writer And Target CSV Loader

**Files:**
- Modify: `src/core/sync_data_authenticity.py`
- Modify: `tests/test_sync_data_authenticity.py`

- [ ] **Step 1: Add failing report tests**

Add tests for:

```python
def test_load_targets_from_difference_csv_filters_forms(tmp_path):
    csv_path = tmp_path / "diff.csv"
    csv_path.write_text("form,db_key,status\n采购订单,1|2,needs_fix\n销售订单,3|4,needs_fix\n", encoding="utf-8-sig")
    targets = load_targets_from_difference_csv(csv_path, {"采购订单"})
    assert targets == {"采购订单": {("1", "2")}}
```

Add a report writer test asserting summary counts include `passed`, `warning_only`, `dimension_mismatch`.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

- [ ] **Step 3: Implement CSV loader and report row helpers**

Implement:

```python
def load_targets_from_difference_csv(path: Path, forms: set[str]) -> dict[str, set[tuple[str, ...]]]:
    ...

def summarize_results(results: list[RowAuditResult]) -> list[dict[str, str | int]]:
    ...

def detail_rows(results: list[RowAuditResult]) -> list[dict[str, str]]:
    ...
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/core/sync_data_authenticity.py tests/test_sync_data_authenticity.py
git commit -m "feat: write sync authenticity reports"
```

### Task 4: Maintenance Script With Injectable Fetchers

**Files:**
- Create: `scripts/maintenance/audit_sync_data_authenticity.py`
- Test: `tests/test_audit_sync_data_authenticity_script.py`

- [ ] **Step 1: Add failing script tests**

Test that the script orchestrator accepts fake DB/API rows and writes reports:

```python
from scripts.maintenance.audit_sync_data_authenticity import run_audit


def test_run_audit_writes_summary_and_detail(tmp_path):
    source = tmp_path / "targets.csv"
    source.write_text("form,db_key,status\n采购订单,1|2,needs_fix\n", encoding="utf-8-sig")
    out_dir = tmp_path / "out"
    db_rows = {"采购订单": {("1", "2"): {"FID": 1, "FENTRYID": 2, "FBillNo": "PO1", "FNUMBER": "A", "FSupplier": "S", "FQTY": "10"}}}
    api_rows = {"采购订单": {("1", "2"): {"FID": 1, "FPOOrderEntry_FENTRYID": 2, "FBillNo": "PO1", "FMaterialId.FNUMBER": "A", "FSupplierId.FNAME": "S", "FQTY": "10"}}}
    result = run_audit(source, {"采购订单"}, out_dir, db_fetcher=lambda *_: db_rows, api_fetcher=lambda *_: api_rows)
    assert result["total"] == 1
    assert (out_dir / "sync_data_authenticity_summary.csv").exists()
    assert (out_dir / "sync_data_authenticity_detail.csv").exists()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_audit_sync_data_authenticity_script.py -q
```

- [ ] **Step 3: Implement script skeleton**

Implement `run_audit()` with injectable fetchers, `argparse` CLI, and default output under `logs/sync_data_authenticity/`.

- [ ] **Step 4: Run script tests**

Run:

```bash
python -m pytest tests/test_audit_sync_data_authenticity_script.py tests/test_sync_data_authenticity.py -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/maintenance/audit_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py
git commit -m "feat: add sync authenticity audit script"
```

### Task 5: Real DB/API Fetchers For Purchase Forms

**Files:**
- Modify: `scripts/maintenance/audit_sync_data_authenticity.py`
- Test: `tests/test_audit_sync_data_authenticity_script.py`

- [ ] **Step 1: Add tests for SQL/API query construction**

Test that `build_db_query()` uses `FID` and `FENTRYID`, and `build_api_filter()` uses `FID IN (...)`.

- [ ] **Step 2: Implement default fetchers**

Use existing project objects:

```python
from src.config.config_manager import config_manager
from src.core.kingdee_api import KingdeeAPIClient
from src.core.mysql_manager import MySQLManager
```

Fetch current DB rows by table and identity keys; fetch API rows by `FormId` config and API identity fields.

- [ ] **Step 3: Run tests**

Run:

```bash
python -m pytest tests/test_audit_sync_data_authenticity_script.py tests/test_sync_data_authenticity.py -q
```

- [ ] **Step 4: Commit**

```bash
git add scripts/maintenance/audit_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py
git commit -m "feat: fetch purchase rows for authenticity audit"
```

### Task 6: Documentation And Verification

**Files:**
- Create: `docs/sync-data-authenticity.md`
- Modify: `openspec/changes/verify-sync-data-authenticity/tasks.md`

- [ ] **Step 1: Document command usage**

Create `docs/sync-data-authenticity.md` with:

```markdown
# 同步数据真实性校验

## Dry-run

python scripts/maintenance/audit_sync_data_authenticity.py --forms 采购入库单,采购订单 --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode dry-run

## Verify

python scripts/maintenance/audit_sync_data_authenticity.py --forms 采购入库单,采购订单 --source logs/all_sync_document_zero_vs_kingdee_detail.csv --mode verify

## 状态含义

- passed: 阻断字段和 warning 字段均一致
- warning_only: 阻断字段一致，日期或状态存在差异
- dimension_mismatch: 阻断维度不一致，禁止自动回灌
- value_mismatch: 修复目标字段不一致，可在阻断字段通过后进入回灌候选
- missing_db: 数据库缺行
- missing_api: 金蝶缺行
```

- [ ] **Step 2: Run full relevant tests**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py tests/test_filter_builder.py tests/test_upsert_engine_sqlserver.py -q
python -m compileall -q src tests scripts
```

Expected: all tests pass and compile succeeds.

- [ ] **Step 3: Mark OpenSpec tasks complete**

Update `openspec/changes/verify-sync-data-authenticity/tasks.md` to mark completed tasks `[x]`.

- [ ] **Step 4: Commit**

```bash
git add docs/sync-data-authenticity.md openspec/changes/verify-sync-data-authenticity/tasks.md
git commit -m "docs: document sync authenticity audit"
```
