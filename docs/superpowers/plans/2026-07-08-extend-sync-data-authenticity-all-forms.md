---
change: extend-sync-data-authenticity-all-forms
design-doc: docs/superpowers/specs/2026-07-08-extend-sync-data-authenticity-all-forms-design.md
base-ref: 98ed7a30a7fa64d9da1ec046db487cc8d3c2b4fa
archived-with: 2026-07-08-extend-sync-data-authenticity-all-forms
---

# All-Form Sync Authenticity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend sync data authenticity from the two purchase forms to all synchronized forms, starting with read-only schema discovery and mapping reports.

**Architecture:** Keep discovery separate from row-level auditing. Discovery reads configuration, optional database columns, and existing `AUDIT_SPECS` to write a mapping draft; the audit script then uses reviewed specs and batches to produce summary/detail/blocker reports without writing SQL Server.

**Tech Stack:** Python standard library, existing `config_manager`, existing `MySQLManager`, pytest.

archived-with: 2026-07-08-extend-sync-data-authenticity-all-forms
---

## File Structure

- Modify `src/core/sync_data_authenticity.py`: add spec metadata, batch constants, blockers report helper, and discovery data classes/functions.
- Modify `scripts/maintenance/audit_sync_data_authenticity.py`: add `--discover`, `--batch`, blockers CSV output, and read-only DB column fetcher.
- Modify `tests/test_sync_data_authenticity.py`: cover spec metadata, unconfirmed identity behavior, inventory snapshot metadata, blockers rows.
- Modify `tests/test_audit_sync_data_authenticity_script.py`: cover discovery CLI helpers and batch/report writing with fakes.
- Modify `docs/sync-data-authenticity.md`: document discovery and all-form dry-run plan.
- Modify `openspec/changes/extend-sync-data-authenticity-all-forms/tasks.md`: mark tasks complete as implementation proceeds.

### Task 1: Discovery Model And Mapping Report

**Files:**
- Modify: `src/core/sync_data_authenticity.py`
- Modify: `tests/test_sync_data_authenticity.py`

- [ ] **Step 1: Write failing tests for discovery rows**

Add tests:

```python
from src.core.sync_data_authenticity import build_mapping_draft_rows


def test_build_mapping_draft_rows_reports_supported_purchase_form():
    form_queries = {
        "采购订单": {"FormId": "PUR_PurchaseOrder", "FieldKeys": "FID,FPOOrderEntry_FENTRYID,FBillNo,FQTY"}
    }
    tables = {"采购订单": {"table": "PUR_PurchaseOrder", "insert_method": "insert_purchase_order"}}
    db_columns = {"PUR_PurchaseOrder": {"FID", "FENTRYID", "FBillNo", "FQTY"}}

    rows = build_mapping_draft_rows(form_queries, tables, db_columns)

    assert rows[0]["form"] == "采购订单"
    assert rows[0]["identity_confirmed"] == "true"
    assert rows[0]["missing_db_fields"] == ""
    assert rows[0]["missing_api_fields"] == ""


def test_build_mapping_draft_rows_marks_unsupported_report_form():
    form_queries = {"科目余额表": {"FormId": "GL_RPT_AccountBalance", "FieldKeys": "FBALANCEID"}}
    tables = {"科目余额表": {"table": "GL_RPT_AccountBalance", "insert_method": None}}

    rows = build_mapping_draft_rows(form_queries, tables, {})

    assert rows[0]["form"] == "科目余额表"
    assert rows[0]["unsupported_reason"] == "report_form_requires_separate_design"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
```

Expected: import failure for `build_mapping_draft_rows`.

- [ ] **Step 3: Implement discovery model**

Add:

```python
FORM_BATCHES = {
    "business_documents": (...),
    "production_documents": (...),
    "snapshot_master_data": (...),
}

UNSUPPORTED_FORMS = {
    "科目余额表": "report_form_requires_separate_design",
}
```

Extend `AuthenticitySpec` with defaulted fields:

```python
identity_confirmed: bool = True
identity_kind: str = "entry"
batch: str = "business_documents"
unsupported_reason: str | None = None
```

Implement:

```python
def build_mapping_draft_rows(form_queries, tables, db_columns, audit_specs=AUDIT_SPECS) -> list[dict[str, str]]:
    ...
```

Rows must include the fields listed in the Design Doc.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
git add src/core/sync_data_authenticity.py tests/test_sync_data_authenticity.py
git commit -m "feat: add authenticity mapping discovery model"
```

### Task 2: Discovery CLI And Read-Only DB Columns

**Files:**
- Modify: `scripts/maintenance/audit_sync_data_authenticity.py`
- Modify: `tests/test_audit_sync_data_authenticity_script.py`

- [ ] **Step 1: Write failing script tests**

Add tests:

```python
from scripts.maintenance.audit_sync_data_authenticity import run_discovery


def test_run_discovery_writes_mapping_draft(tmp_path):
    form_queries = {"采购订单": {"FormId": "PUR_PurchaseOrder", "FieldKeys": "FID,FPOOrderEntry_FENTRYID,FBillNo"}}
    tables = {"采购订单": {"table": "PUR_PurchaseOrder", "insert_method": "insert_purchase_order"}}
    db_columns = {"PUR_PurchaseOrder": {"FID", "FENTRYID", "FBillNo"}}

    result = run_discovery(tmp_path, form_queries=form_queries, tables=tables, db_columns=db_columns)

    assert result["rows"] == 1
    assert (tmp_path / "authenticity_mapping_draft.csv").exists()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_audit_sync_data_authenticity_script.py -q
```

Expected: import failure for `run_discovery`.

- [ ] **Step 3: Implement read-only discovery command**

Implement:

```python
def fetch_db_columns() -> dict[str, set[str]]:
    ...

def run_discovery(out_dir, form_queries=None, tables=None, db_columns=None) -> dict[str, object]:
    ...
```

CLI additions:

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --discover --out-dir logs/sync_data_authenticity
```

`fetch_db_columns()` may execute only `INFORMATION_SCHEMA.COLUMNS` SELECT statements.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python -m pytest tests/test_audit_sync_data_authenticity_script.py tests/test_sync_data_authenticity.py -q
git add scripts/maintenance/audit_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py
git commit -m "feat: add read-only authenticity discovery report"
```

### Task 3: Batches And Blockers Report

**Files:**
- Modify: `src/core/sync_data_authenticity.py`
- Modify: `scripts/maintenance/audit_sync_data_authenticity.py`
- Modify: tests

- [ ] **Step 1: Write failing tests**

Add tests for:

```python
from src.core.sync_data_authenticity import blocker_rows


def test_blocker_rows_excludes_passed_rows():
    ...
```

And script tests that `run_audit(..., write_blockers=True)` writes `sync_data_authenticity_blockers.csv`.

- [ ] **Step 2: Implement blockers and batch filtering**

Add:

```python
BLOCKER_STATUSES = {
    AuditStatus.MISSING_DB,
    AuditStatus.MISSING_API,
    AuditStatus.IDENTITY_MISMATCH,
    AuditStatus.DIMENSION_MISMATCH,
    AuditStatus.VALUE_MISMATCH,
}

def blocker_rows(results: list[RowAuditResult]) -> list[dict[str, str]]:
    ...
```

CLI additions:

```bash
--batch business_documents
--batch production_documents
--batch snapshot_master_data
```

- [ ] **Step 3: Run tests and commit**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py -q
git add src/core/sync_data_authenticity.py scripts/maintenance/audit_sync_data_authenticity.py tests
git commit -m "feat: add batch and blocker reports for authenticity audit"
```

### Task 4: Initial All-Form Spec Metadata

**Files:**
- Modify: `src/core/sync_data_authenticity.py`
- Modify: `tests/test_sync_data_authenticity.py`

- [ ] **Step 1: Add tests for form coverage metadata**

Test that discovery rows contain all synchronized forms except unsupported report form, and that `即时库存` has `identity_kind == "snapshot"`.

- [ ] **Step 2: Add initial specs and unconfirmed markers**

Add `AuthenticitySpec` entries for:

```text
销售订单, 销售出库单, 销售退货单, 发货通知单, 生产入库单, 生产订单主表,
生产订单明细, 生产用料清单主表, 生产用料清单明细表, 预测订单, 委外订单,
应付单, 应收单, 即时库存, 客户资料, 物料, 仓库, 物料清单, 物料清单子项
```

Forms with uncertain identity must set `identity_confirmed=False`.

- [ ] **Step 3: Run tests and commit**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py -q
git add src/core/sync_data_authenticity.py tests/test_sync_data_authenticity.py
git commit -m "feat: add all-form authenticity spec metadata"
```

### Task 5: Documentation, Discovery Execution, And OpenSpec Tasks

**Files:**
- Modify: `docs/sync-data-authenticity.md`
- Modify: `openspec/changes/extend-sync-data-authenticity-all-forms/tasks.md`

- [ ] **Step 1: Update documentation**

Document:

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --discover --out-dir logs/sync_data_authenticity
python scripts/maintenance/audit_sync_data_authenticity.py --batch business_documents --source <source.csv> --mode dry-run
```

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest tests/test_sync_data_authenticity.py tests/test_audit_sync_data_authenticity_script.py tests/test_filter_builder.py tests/test_upsert_engine_sqlserver.py -q
python -m compileall -q src tests scripts
```

- [ ] **Step 3: Execute discovery only**

Run:

```bash
python scripts/maintenance/audit_sync_data_authenticity.py --discover --out-dir logs/sync_data_authenticity
```

Expected:

```text
discovery: wrote logs/sync_data_authenticity/authenticity_mapping_draft.csv
```

- [ ] **Step 4: Mark tasks and commit**

Mark all OpenSpec tasks complete and commit:

```bash
git add docs/sync-data-authenticity.md openspec/changes/extend-sync-data-authenticity-all-forms/tasks.md
git commit -m "docs: document all-form authenticity discovery"
```
