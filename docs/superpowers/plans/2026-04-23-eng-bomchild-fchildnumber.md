# ENG_BOMCHILD FCHILDNUMBER Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `FMATERIALIDCHILD.FNUMBER` to the BOM child sync path, persist it as `eng_bomchild.FCHILDNUMBER`, create the live SQL Server column, and reorder `eng_bomchild` to the recommended column layout.

**Architecture:** Use TDD to lock the three risky areas first: payload mapping, SQL Server writer/schema guard, and SQL Server staging SQL. Keep the implementation minimal by updating the existing JSON query config, `MySQLManager` mapping/helpers, the existing `insert_eng_bom_child` writer, and the existing SQL Server business layout script. After code is green, connect through the repo's existing `mysql_manager` to create the live column and run the existing reorder script against `eng_bomchild`.

**Tech Stack:** Python, unittest, JSON config, SQL Server, pyodbc, PowerShell

---

### Task 1: Add FCHILDNUMBER ingestion and schema guard

**Files:**
- Create: `D:\Kingdee\tests\test_eng_bomchild_field_mapping.py`
- Modify: `D:\Kingdee\src\config\form-queries.json`
- Modify: `D:\Kingdee\dotnet\form-queries.json`
- Modify: `D:\Kingdee\src\core\mysql_manager.py`
- Modify: `D:\Kingdee\src\core\masterdata_writer.py`

- [ ] **Step 1: Write the failing field-mapping test file**

```python
from __future__ import annotations

import unittest

from src.core.mysql_manager import MySQLManager


class FakeCursor:
    def __init__(self, fetchone_results: list[object]) -> None:
        self.fetchone_results = list(fetchone_results)
        self.execute_calls: list[tuple[str, object]] = []

    def execute(self, sql: str, params=None) -> None:
        self.execute_calls.append((sql, params))

    def fetchone(self):
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.commit_count = 0

    def commit(self) -> None:
        self.commit_count += 1


class EngBomChildFieldMappingTests(unittest.TestCase):
    def _build_manager(self) -> MySQLManager:
        manager = MySQLManager.__new__(MySQLManager)
        manager.connection = None
        manager.cursor = None
        manager.db_type = "sqlserver"
        return manager

    def test_prepare_eng_bom_child_data_reads_child_number_from_dict_payload(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 1001,
                "FTreeEntity_FENTRYID": 2002,
                "FTreeEntity_FSEQ": 1,
                "FMATERIALID": "MAT-001",
                "FMATERIALIDCHILD.FNUMBER": "CHILD-001",
                "FNUMERATOR": 2,
                "FDENOMINATOR": 1,
                "FISSUETYPE": "1",
                "FBACKFLUSHTYPE": "2",
                "FSUPPLYORG": 900,
                "FSTOCKID": 800,
                "FENTRYROWID": "ROW-1",
                "FREPLACEGROUP": 0,
                "FQTY": 5,
                "FACTUALQTY": 4,
                "FMASTERID": 700,
                "FMATERIALTYPE": "RM",
                "FMODIFYDATE": "2026-04-23 10:11:12",
            }
        )

        self.assertEqual(prepared[3], "MAT-001")
        self.assertEqual(prepared[4], "CHILD-001")
        self.assertEqual(prepared[16], "RM")

    def test_prepare_eng_bom_child_data_reads_child_number_from_list_payload(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            [
                1001,
                2002,
                1,
                "MAT-001",
                "CHILD-001",
                2,
                1,
                "1",
                "2",
                900,
                800,
                "ROW-1",
                0,
                5,
                4,
                700,
                "RM",
                "2026-04-23 10:11:12",
            ]
        )

        self.assertEqual(prepared[3], "MAT-001")
        self.assertEqual(prepared[4], "CHILD-001")
        self.assertEqual(prepared[16], "RM")

    def test_ensure_additional_columns_for_eng_bomchild_adds_child_number_column_on_sqlserver(self) -> None:
        manager = self._build_manager()
        manager.cursor = FakeCursor(fetchone_results=[None])
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = lambda _table: None

        manager._ensure_additional_columns_for_eng_bomchild()

        self.assertEqual(manager.connection.commit_count, 1)
        self.assertEqual(len(manager.cursor.execute_calls), 2)
        self.assertIn("INFORMATION_SCHEMA.COLUMNS", manager.cursor.execute_calls[0][0])
        self.assertIn(
            "ALTER TABLE eng_bomchild ADD FCHILDNUMBER NVARCHAR(255) NULL",
            manager.cursor.execute_calls[1][0],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test file and verify it fails**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping -v
```

Expected: `FAIL` or `ERROR` because `FCHILDNUMBER` is not mapped yet and `_ensure_additional_columns_for_eng_bomchild()` does not exist yet.

- [ ] **Step 3: Add `FMATERIALIDCHILD.FNUMBER` to both query config files**

```json
"FieldKeys": "FID,FTreeEntity_FENTRYID,FTreeEntity_FSEQ,FMATERIALID,FMATERIALIDCHILD.FNUMBER,FNUMERATOR,FDENOMINATOR,FISSUETYPE,FBACKFLUSHTYPE,FSUPPLYORG,FSTOCKID,FENTRYROWID,FREPLACEGROUP,FQTY,FACTUALQTY,FMASTERID,FMATERIALTYPE,FMODIFYDATE",
```

- [ ] **Step 4: Add the new SQL Server/MySQL schema guard in `MySQLManager`**

```python
    def _ensure_additional_columns_for_eng_bomchild(self) -> None:
        """Ensure eng_bomchild has the child material number column required by sync."""
        try:
            table = "eng_bomchild"
            column = "FCHILDNUMBER"
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"

            if is_sqlserver:
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                    (table, column),
                )
            else:
                self.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                    (table, column),
                )

            if self.cursor.fetchone():
                return

            if is_sqlserver:
                self.cursor.execute(f"ALTER TABLE {table} ADD {column} NVARCHAR(255) NULL")
            else:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(255) NULL")

            try:
                self.connection.commit()
            except Exception:
                pass
            self._invalidate_table_metadata_cache(table)
            logger.info(f"Created column {table}.{column}")
        except Exception as e:
            logger.debug(f"Failed to ensure eng_bomchild child number column: {e}")
```

- [ ] **Step 5: Update `_prepare_eng_bom_child_data()` to map the new field in both dict and list modes**

```python
            if isinstance(item, dict):
                return (
                    (self._to_int_or_none(item.get("FID") or 0) or item.get("FId")),
                    (self._to_int_or_none(item.get("FTreeEntity_FENTRYID") or 0) or item.get("FENTRYID")),
                    (self._to_int_or_none(item.get("FTreeEntity_FSEQ") or 0) or item.get("FSEQ")),
                    self._safe_str(item.get("FMATERIALID") or item.get("FTreeEntity_FMATERIALID")),
                    self._safe_str(
                        item.get("FMATERIALIDCHILD.FNUMBER")
                        or item.get("FMATERIALIDCHILD.FNumber")
                        or item.get("FCHILDNUMBER")
                    ),
                    (self._to_decimal_or_none(item.get("FNUMERATOR") or 0.0)),
                    (self._to_decimal_or_none(item.get("FDENOMINATOR") or 0.0)),
                    self._safe_str(item.get("FISSUETYPE")),
                    self._safe_str(item.get("FBACKFLUSHTYPE")),
                    self._to_int_or_none(item.get("FSUPPLYORG")) or 0,
                    self._to_int_or_none(item.get("FSTOCKID") or item.get("FStockId")) or 0,
                    self._safe_str(item.get("FENTRYROWID")),
                    (self._to_int_or_none(item.get("FREPLACEGROUP") or 0)),
                    (self._to_decimal_or_none(item.get("FQTY") or 0.0) or item.get("FTreeEntity_FQTY")),
                    (self._to_decimal_or_none(item.get("FACTUALQTY") or 0.0)),
                    (self._to_int_or_none(item.get("FMASTERID") or 0)),
                    self._safe_str(item.get("FMATERIALTYPE") or item.get("FTreeEntity_FMATERIALTYPE")),
                    self._parse_datetime(item.get("FMODIFYDATE") or item.get("FModifyDate")),
                )
            elif isinstance(item, list) and len(item) >= 17:
                fmodifydate = self._parse_datetime(item[17]) if len(item) > 17 else None
                return (
                    (self._to_int_or_none(item[0]) or 0),
                    (self._to_int_or_none(item[1]) or 0),
                    (self._to_int_or_none(item[2]) or 0),
                    self._safe_str(item[3]),
                    self._safe_str(item[4]),
                    (self._to_decimal_or_none(item[5]) or 0.0),
                    (self._to_decimal_or_none(item[6]) or 0.0),
                    self._safe_str(item[7]),
                    self._safe_str(item[8]),
                    self._to_int_or_none(item[9]) or 0,
                    self._to_int_or_none(item[10]) or 0,
                    self._safe_str(item[11]),
                    (self._to_int_or_none(item[12]) or 0),
                    (self._to_decimal_or_none(item[13]) or 0.0),
                    (self._to_decimal_or_none(item[14]) or 0.0),
                    (self._to_int_or_none(item[15]) or 0),
                    self._safe_str(item[16]),
                    fmodifydate,
                )
```

- [ ] **Step 6: Update `insert_eng_bom_child()` to ensure the column and write `FCHILDNUMBER`**

```python
        try:
            manager._ensure_additional_columns_for_eng_bomchild()

            sql = """
                INSERT INTO eng_bomchild
                (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FSEQ = VALUES(FSEQ),
                    FMATERIALID = VALUES(FMATERIALID),
                    FCHILDNUMBER = VALUES(FCHILDNUMBER),
                    FNUMERATOR = VALUES(FNUMERATOR),
                    FDENOMINATOR = VALUES(FDENOMINATOR),
                    FISSUETYPE = VALUES(FISSUETYPE),
                    FBACKFLUSHTYPE = VALUES(FBACKFLUSHTYPE),
                    FSUPPLYORG = VALUES(FSUPPLYORG),
                    FSTOCKID = VALUES(FSTOCKID),
                    FENTRYROWID = VALUES(FENTRYROWID),
                    FREPLACEGROUP = VALUES(FREPLACEGROUP),
                    FQTY = VALUES(FQTY),
                    FACTUALQTY = VALUES(FACTUALQTY),
                    FMASTERID = VALUES(FMASTERID),
                    FMATERIALTYPE = VALUES(FMATERIALTYPE),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_eng_bom_child_data)
```

- [ ] **Step 7: Run the field-mapping test file again and verify it passes**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping -v
```

Expected: `OK`

- [ ] **Step 8: Commit**

```powershell
git add tests/test_eng_bomchild_field_mapping.py src/config/form-queries.json dotnet/form-queries.json src/core/mysql_manager.py src/core/masterdata_writer.py
git commit -m "feat: add eng_bomchild child number mapping"
```

### Task 2: Align the recommended SQL Server column order

**Files:**
- Modify: `D:\Kingdee\tests\test_sqlserver_business_layout.py`
- Modify: `D:\Kingdee\src\tools\sqlserver_business_layout.py`

- [ ] **Step 1: Update the layout test first so it fails on the missing order slot**

```python
    def test_eng_bomchild_moves_material_block_forward(self) -> None:
        existing = [
            "FID",
            "FENTRYID",
            "FSEQ",
            "FNUMERATOR",
            "FDENOMINATOR",
            "FISSUETYPE",
            "FBACKFLUSHTYPE",
            "FSUPPLYORG",
            "FSTOCKID",
            "FENTRYROWID",
            "FREPLACEGROUP",
            "FACTUALQTY",
            "FMASTERID",
            "FMATERIALID",
            "FQTY",
            "SYNC_TIME",
            "FMATERIALTYPE",
            "FMODIFYDATE",
            "FCHILDNUMBER",
        ]

        ordered = resolve_desired_order("eng_bomchild", existing)

        self.assertEqual(
            ordered,
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FMASTERID",
                "FMATERIALID",
                "FCHILDNUMBER",
                "FMATERIALTYPE",
                "FNUMERATOR",
                "FDENOMINATOR",
                "FQTY",
                "FACTUALQTY",
                "FISSUETYPE",
                "FBACKFLUSHTYPE",
                "FSUPPLYORG",
                "FSTOCKID",
                "FENTRYROWID",
                "FREPLACEGROUP",
                "FMODIFYDATE",
                "SYNC_TIME",
            ],
        )
```

- [ ] **Step 2: Run the layout test and verify it fails**

Run:

```powershell
python -m unittest tests.test_sqlserver_business_layout.SqlServerBusinessLayoutTests.test_eng_bomchild_moves_material_block_forward -v
```

Expected: `FAIL` because `resolve_desired_order("eng_bomchild", ...)` still puts `FCHILDNUMBER` at the end.

- [ ] **Step 3: Insert `FCHILDNUMBER` into the `eng_bomchild` business order list**

```python
    "eng_bomchild": [
        "FID",
        "FENTRYID",
        "FSEQ",
        "FMASTERID",
        "FMATERIALID",
        "FCHILDNUMBER",
        "FMATERIALTYPE",
        "FNUMERATOR",
        "FDENOMINATOR",
        "FQTY",
        "FACTUALQTY",
        "FISSUETYPE",
        "FBACKFLUSHTYPE",
        "FSUPPLYORG",
        "FSTOCKID",
        "FENTRYROWID",
        "FREPLACEGROUP",
        "FMODIFYDATE",
        "SYNC_TIME",
    ],
```

- [ ] **Step 4: Re-run the layout test and verify it passes**

Run:

```powershell
python -m unittest tests.test_sqlserver_business_layout.SqlServerBusinessLayoutTests.test_eng_bomchild_moves_material_block_forward -v
```

Expected: `OK`

- [ ] **Step 5: Commit**

```powershell
git add tests/test_sqlserver_business_layout.py src/tools/sqlserver_business_layout.py
git commit -m "feat: order eng_bomchild child number column"
```

### Task 3: Align SQL Server staging with the new writer column list

**Files:**
- Modify: `D:\Kingdee\tests\test_upsert_engine_sqlserver.py`
- Modify: `D:\Kingdee\src\core\upsert_engine_sqlserver.py`

- [ ] **Step 1: Extend the SQL Server test doubles so a staging-path test can run**

```python
class FakeCursor:
    def __init__(self) -> None:
        self.fast_executemany = False
        self._fetchall_queue: list[list[object]] = []
        self._fetchone_queue: list[object] = []
        self.execute_calls: list[tuple[str, object]] = []
        self.executemany_calls: list[tuple[str, list[list[object]]]] = []

    def execute(self, sql: str, params=None) -> None:
        self.execute_calls.append((sql, params))

    def executemany(self, sql: str, params) -> None:
        self.executemany_calls.append((sql, list(params)))

    def fetchall(self):
        if self._fetchall_queue:
            return self._fetchall_queue.pop(0)
        return []

    def fetchone(self):
        if self._fetchone_queue:
            return self._fetchone_queue.pop(0)
        return None


class FakeSqlServerManager:
    def __init__(self) -> None:
        self.db_type = "sqlserver"
        self.config = {
            "driver": "ODBC Driver 17 for SQL Server",
            "insert_threads": "1",
            "use_staging": "false",
            "batch_size": "10000",
            "commit_every_n_batches": "0",
            "source_dedup_enabled": "true",
        }
        self.cursor = FakeCursor()
        self.connection = FakeConnection()

    def _maybe_create_stage_index(self, stage_ref, base_name, pk_cols, loaded) -> None:
        return None
```

- [ ] **Step 2: Add a failing test that forces `eng_bomchild` down the staging branch**

```python
    def test_eng_bomchild_staging_sql_includes_child_number(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["use_staging"] = "true"
        manager.config["force_staging_tables"] = "eng_bomchild"
        manager.cursor._fetchone_queue = [(1,)]
        manager._parse_insert_sql = lambda sql: (
            "eng_bomchild",
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FMATERIALID",
                "FCHILDNUMBER",
                "FNUMERATOR",
                "FDENOMINATOR",
                "FISSUETYPE",
                "FBACKFLUSHTYPE",
                "FSUPPLYORG",
                "FSTOCKID",
                "FENTRYROWID",
                "FREPLACEGROUP",
                "FQTY",
                "FACTUALQTY",
                "FMASTERID",
                "FMATERIALTYPE",
                "FMODIFYDATE",
            ],
        )
        manager._get_table_columns_info = lambda table: {
            "FID": "int",
            "FENTRYID": "int",
            "FSEQ": "int",
            "FMATERIALID": "nvarchar",
            "FCHILDNUMBER": "nvarchar",
            "FNUMERATOR": "decimal",
            "FDENOMINATOR": "decimal",
            "FISSUETYPE": "nvarchar",
            "FBACKFLUSHTYPE": "nvarchar",
            "FSUPPLYORG": "int",
            "FSTOCKID": "int",
            "FENTRYROWID": "nvarchar",
            "FREPLACEGROUP": "int",
            "FQTY": "decimal",
            "FACTUALQTY": "decimal",
            "FMASTERID": "int",
            "FMATERIALTYPE": "nvarchar",
            "FMODIFYDATE": "datetime",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FID,FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO eng_bomchild (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            values=[[1001, 2002, 1, "MAT-001", "CHILD-001", 2, 1, "1", "2", 900, 800, "ROW-1", 0, 5, 4, 700, "RM", "2026-04-23 10:11:12"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        stage_insert_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("FCHILDNUMBER", stage_insert_sql)
        self.assertIn("TRY_CAST(? AS NVARCHAR(255))", stage_insert_sql)
```

- [ ] **Step 3: Run the new staging test and verify it fails**

Run:

```powershell
python -m unittest tests.test_upsert_engine_sqlserver.UpsertEngineSqlServerTests.test_eng_bomchild_staging_sql_includes_child_number -v
```

Expected: `FAIL` because the hard-coded `eng_bomchild` staging SQL still omits `FCHILDNUMBER`.

- [ ] **Step 4: Add `FCHILDNUMBER` to the hard-coded `eng_bomchild` staging SQL**

```python
                            elif base_name.strip().lower() == "eng_bomchild":
                                insert_stage_sql = (
                                    f"INSERT INTO {stage_ref} (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, "
                                    f"FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) "
                                    f"SELECT "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS NVARCHAR(64)), "
                                    f"TRY_CAST(? AS NVARCHAR(255)), "
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "
                                    f"TRY_CAST(? AS NVARCHAR(32)), "
                                    f"TRY_CAST(? AS NVARCHAR(32)), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS NVARCHAR(50)), "
                                    f"TRY_CAST(? AS INT), "
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "
                                    f"COALESCE(TRY_CAST(? AS DECIMAL(23,10)), 0), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS NVARCHAR(32)), "
                                    f"TRY_CAST(? AS DATETIME)"
                                )
```

- [ ] **Step 5: Run the staging test again and verify it passes**

Run:

```powershell
python -m unittest tests.test_upsert_engine_sqlserver.UpsertEngineSqlServerTests.test_eng_bomchild_staging_sql_includes_child_number -v
```

Expected: `OK`

- [ ] **Step 6: Commit**

```powershell
git add tests/test_upsert_engine_sqlserver.py src/core/upsert_engine_sqlserver.py
git commit -m "fix: align eng_bomchild staging with child number"
```

### Task 4: Run integrated tests and create the live SQL Server column

**Files:**
- Reference: `D:\Kingdee\docs\superpowers\specs\2026-04-23-eng-bomchild-fchildnumber-design.md`
- Reference: `D:\Kingdee\src\core\mysql_manager.py`

- [ ] **Step 1: Run the full related test set**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping tests.test_sqlserver_business_layout tests.test_upsert_engine_sqlserver -v
```

Expected: `OK`

- [ ] **Step 2: Connect through the repo's SQL Server manager and create the live column**

Run:

```powershell
@'
from src.core.mysql_manager import mysql_manager

if not mysql_manager.connection or not mysql_manager.cursor:
    if not mysql_manager.connect():
        raise SystemExit("connect failed")

mysql_manager._ensure_additional_columns_for_eng_bomchild()
print(mysql_manager._table_has_column("eng_bomchild", "FCHILDNUMBER"))
'@ | python -
```

Expected: `True`

- [ ] **Step 3: Verify the live SQL Server table really has the new column**

Run:

```powershell
@'
from src.core.mysql_manager import mysql_manager

if not mysql_manager.connection or not mysql_manager.cursor:
    if not mysql_manager.connect():
        raise SystemExit("connect failed")

mysql_manager.cursor.execute(
    """
    SELECT COLUMN_NAME, DATA_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
    """,
    ("eng_bomchild", "FCHILDNUMBER"),
)
print(mysql_manager.cursor.fetchall())
'@ | python -
```

Expected: one row containing `FCHILDNUMBER` and `nvarchar`

- [ ] **Step 4: Confirm the expected runtime logging outcome**

Checklist:

```text
[x] First sync can log that eng_bomchild.FCHILDNUMBER was created
[x] Later syncs should not log "[eng_bomchild] target db missing columns ignored: ['FCHILDNUMBER']"
[x] No key/index changes are required for FID,FENTRYID
```

### Task 5: Dry-run and apply the SQL Server reorder

**Files:**
- Reference: `D:\Kingdee\scripts\reorder_sqlserver_business_tables.py`
- Reference: `D:\Kingdee\src\tools\sqlserver_business_layout.py`

- [ ] **Step 1: Run the reorder script in dry-run mode after the live column exists**

Run:

```powershell
python scripts/reorder_sqlserver_business_tables.py --tables eng_bomchild
```

Expected: output contains a `desired:` line with `FID, FENTRYID, FSEQ, FMASTERID, FMATERIALID, FCHILDNUMBER, FMATERIALTYPE`

- [ ] **Step 2: Execute the actual reorder**

Run:

```powershell
python scripts/reorder_sqlserver_business_tables.py --execute --tables eng_bomchild
```

Expected: output ends with `applied: eng_bomchild` and no row-count mismatch error

- [ ] **Step 3: Verify the three-column material block order in SQL Server**

Run:

```powershell
@'
from src.core.mysql_manager import mysql_manager

if not mysql_manager.connection or not mysql_manager.cursor:
    if not mysql_manager.connect():
        raise SystemExit("connect failed")

mysql_manager.cursor.execute(
    """
    SELECT COLUMN_NAME, ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = ?
      AND COLUMN_NAME IN ('FMATERIALID', 'FCHILDNUMBER', 'FMATERIALTYPE')
    ORDER BY ORDINAL_POSITION
    """,
    ("eng_bomchild",),
)
for row in mysql_manager.cursor.fetchall():
    print(row)
'@ | python -
```

Expected:

```text
('FMATERIALID', <n>)
('FCHILDNUMBER', <n+1>)
('FMATERIALTYPE', <n+2>)
```

- [ ] **Step 4: Run the final verification commands**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping tests.test_sqlserver_business_layout tests.test_upsert_engine_sqlserver -v
python scripts/reorder_sqlserver_business_tables.py --tables eng_bomchild
```

Expected: tests are green, and the dry-run now shows either matching `current`/`desired` output or an explicit skip because the table order is already correct
