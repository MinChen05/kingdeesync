# ENG_BOMCHILD FCHILDNAME Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `FMATERIALIDCHILD.FNAME` to the BOM child sync path, persist it as `eng_bomchild.FCHILDNAME`, create the live SQL Server column, reorder `eng_bomchild` to the recommended layout, and backfill data through a safe full sync.

**Architecture:** Reuse the existing `FCHILDNUMBER` path as the reference implementation and apply the same pattern to `FCHILDNAME`. Use TDD to lock the three risky points first: payload mapping/schema guard, SQL Server layout order, and the hard-coded `eng_bomchild` staging SQL. After code is green, create the live column with the existing `mysql_manager`, run the SQL Server reorder script, then run a targeted `full` sync for `物料清单子项` to backfill `FCHILDNAME` without truncating the table.

**Tech Stack:** Python, unittest, JSON config, SQL Server, pyodbc, PowerShell

---

### Task 1: Add FCHILDNAME ingestion, schema guard, and writer support

**Files:**
- Modify: `D:\Kingdee\tests\test_eng_bomchild_field_mapping.py`
- Modify: `D:\Kingdee\src\config\form-queries.json`
- Modify: `D:\Kingdee\dotnet\form-queries.json`
- Modify: `D:\Kingdee\src\core\mysql_manager.py`
- Modify: `D:\Kingdee\src\core\masterdata_writer.py`

- [ ] **Step 1: Write the failing tests for child name mapping and schema guard**

```python
    def test_prepare_eng_bom_child_data_reads_child_name_from_dict_payload(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 101,
                "FTreeEntity_FENTRYID": 202,
                "FTreeEntity_FSEQ": 3,
                "FMATERIALID": "MAT-PARENT",
                "FMATERIALIDCHILD.FNUMBER": "MAT-CHILD-001",
                "FMATERIALIDCHILD.FNAME": "子项名称A",
                "FNUMERATOR": "2",
                "FDENOMINATOR": "1",
                "FMATERIALTYPE": "1",
            }
        )

        self.assertEqual(prepared[4], "MAT-CHILD-001")
        self.assertEqual(prepared[5], "子项名称A")
        self.assertEqual(prepared[17], "1")

    def test_prepare_eng_bom_child_data_reads_child_name_from_list_payload(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            [
                101,
                202,
                3,
                "MAT-PARENT",
                "MAT-CHILD-002",
                "子项名称B",
                "2",
                "1",
                "1",
                "2",
                171190,
                88,
                "ROW-2",
                0,
                "7.5",
                "7.0",
                303,
                "2",
                "2026-04-24 09:30:00",
            ]
        )

        self.assertEqual(prepared[4], "MAT-CHILD-002")
        self.assertEqual(prepared[5], "子项名称B")
        self.assertEqual(prepared[17], "2")

    def test_prepare_eng_bom_child_data_reads_child_name_from_fchildname_fallback(self) -> None:
        manager = self._build_manager()

        prepared = manager._prepare_eng_bom_child_data(
            {
                "FID": 101,
                "FTreeEntity_FENTRYID": 202,
                "FTreeEntity_FSEQ": 3,
                "FMATERIALID": "MAT-PARENT",
                "FCHILDNAME": "子项名称C",
                "FMATERIALTYPE": "3",
            }
        )

        self.assertEqual(prepared[5], "子项名称C")
```

- [ ] **Step 2: Extend the schema-guard tests to cover `FCHILDNAME`**

```python
    def test_ensure_additional_columns_for_eng_bomchild_adds_child_name_column_on_sqlserver(self) -> None:
        manager = self._build_manager()
        manager.cursor = FakeCursor(fetchone_results=[None, None])
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = lambda _table: None

        manager._ensure_additional_columns_for_eng_bomchild()

        self.assertIn(
            "ALTER TABLE eng_bomchild ADD FCHILDNAME NVARCHAR(255) NULL",
            manager.cursor.execute_calls[2][0],
        )

    def test_ensure_additional_columns_for_eng_bomchild_adds_child_name_column_on_mysql(self) -> None:
        manager = self._build_manager()
        manager.db_type = "mysql"
        manager.cursor = FakeCursor(fetchone_results=[None, None])
        manager.connection = FakeConnection()
        manager._invalidate_table_metadata_cache = lambda _table: None

        manager._ensure_additional_columns_for_eng_bomchild()

        self.assertIn(
            "ALTER TABLE eng_bomchild ADD COLUMN FCHILDNAME VARCHAR(255) NULL",
            manager.cursor.execute_calls[2][0],
        )
```

- [ ] **Step 3: Run the field-mapping test file and verify it fails for the expected reasons**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping -v
```

Expected: `FAIL` or `ERROR` because `FCHILDNAME` is not yet mapped and the schema guard does not yet add that column.

- [ ] **Step 4: Add `FMATERIALIDCHILD.FNAME` to both query config files right after `FMATERIALIDCHILD.FNUMBER`**

```json
"FieldKeys": "FID,FTreeEntity_FENTRYID,FTreeEntity_FSEQ,FMATERIALID,FMATERIALIDCHILD.FNUMBER,FMATERIALIDCHILD.FNAME,FNUMERATOR,FDENOMINATOR,FISSUETYPE,FBACKFLUSHTYPE,FSUPPLYORG,FSTOCKID,FENTRYROWID,FREPLACEGROUP,FQTY,FACTUALQTY,FMASTERID,FMATERIALTYPE,FMODIFYDATE",
```

- [ ] **Step 5: Extend `_ensure_additional_columns_for_eng_bomchild()` to add `FCHILDNAME` in both SQL Server and MySQL**

```python
    def _ensure_additional_columns_for_eng_bomchild(self) -> None:
        """确保 eng_bomchild 存在当前同步依赖的扩展字段。"""
        try:
            table = "eng_bomchild"
            child_columns = (
                ("FCHILDNUMBER", "NVARCHAR(255)", "VARCHAR(255)"),
                ("FCHILDNAME", "NVARCHAR(255)", "VARCHAR(255)"),
            )
            is_sqlserver = getattr(self, "db_type", "mysql") == "sqlserver"

            for column, sqlserver_type, mysql_type in child_columns:
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
                    continue

                if is_sqlserver:
                    self.cursor.execute(f"ALTER TABLE {table} ADD {column} {sqlserver_type} NULL")
                else:
                    self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {mysql_type} NULL")

            try:
                self.connection.commit()
            except Exception:
                pass
            self._invalidate_table_metadata_cache(table)
        except Exception as e:
            logger.error(f"检查或新增 eng_bomchild 扩展字段失败: {e}")
```

- [ ] **Step 6: Update `_prepare_eng_bom_child_data()` to map `FCHILDNAME` in both dict and list modes**

```python
            if isinstance(item, dict):
                child_number = (
                    item.get("FMATERIALIDCHILD.FNUMBER")
                    or item.get("FMATERIALIDCHILD.FNumber")
                    or item.get("FCHILDNUMBER")
                )
                child_name = (
                    item.get("FMATERIALIDCHILD.FNAME")
                    or item.get("FMATERIALIDCHILD.FName")
                    or item.get("FCHILDNAME")
                )
                return (
                    (self._to_int_or_none(item.get("FID") or 0) or item.get("FId")),
                    (self._to_int_or_none(item.get("FTreeEntity_FENTRYID") or 0) or item.get("FENTRYID")),
                    (self._to_int_or_none(item.get("FTreeEntity_FSEQ") or 0) or item.get("FSEQ")),
                    self._safe_str(item.get("FMATERIALID") or item.get("FTreeEntity_FMATERIALID")),
                    self._safe_str(child_number),
                    self._safe_str(child_name),
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
            elif isinstance(item, list) and len(item) >= 18:
                fmodifydate = self._parse_datetime(item[18]) if len(item) > 18 else None
                return (
                    (self._to_int_or_none(item[0]) or 0),
                    (self._to_int_or_none(item[1]) or 0),
                    (self._to_int_or_none(item[2]) or 0),
                    self._safe_str(item[3]),
                    self._safe_str(item[4]),
                    self._safe_str(item[5]),
                    (self._to_decimal_or_none(item[6]) or 0.0),
                    (self._to_decimal_or_none(item[7]) or 0.0),
                    self._safe_str(item[8]),
                    self._safe_str(item[9]),
                    self._to_int_or_none(item[10]) or 0,
                    self._to_int_or_none(item[11]) or 0,
                    self._safe_str(item[12]),
                    (self._to_int_or_none(item[13]) or 0),
                    (self._to_decimal_or_none(item[14]) or 0.0),
                    (self._to_decimal_or_none(item[15]) or 0.0),
                    (self._to_int_or_none(item[16]) or 0),
                    self._safe_str(item[17]),
                    fmodifydate,
                )
```

- [ ] **Step 7: Update `insert_eng_bom_child()` to write `FCHILDNAME`**

```python
        try:
            manager._ensure_additional_columns_for_eng_bomchild()

            sql = """
                INSERT INTO eng_bomchild
                (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FSEQ = VALUES(FSEQ),
                    FMATERIALID = VALUES(FMATERIALID),
                    FCHILDNUMBER = VALUES(FCHILDNUMBER),
                    FCHILDNAME = VALUES(FCHILDNAME),
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
```

- [ ] **Step 8: Run the field-mapping tests again and verify they pass**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping -v
```

Expected: `OK`

- [ ] **Step 9: Commit**

```powershell
git add tests/test_eng_bomchild_field_mapping.py src/config/form-queries.json dotnet/form-queries.json src/core/mysql_manager.py src/core/masterdata_writer.py
git commit -m "feat: add eng_bomchild child name mapping"
```

### Task 2: Insert FCHILDNAME into the recommended SQL Server column order

**Files:**
- Modify: `D:\Kingdee\tests\test_sqlserver_business_layout.py`
- Modify: `D:\Kingdee\src\tools\sqlserver_business_layout.py`

- [ ] **Step 1: Update the layout test first so it fails**

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
            "FCHILDNUMBER",
            "FQTY",
            "SYNC_TIME",
            "FMATERIALTYPE",
            "FMODIFYDATE",
            "FCHILDNAME",
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
                "FCHILDNAME",
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

Expected: `FAIL` because `FCHILDNAME` is still preserved at the end.

- [ ] **Step 3: Insert `FCHILDNAME` into the `eng_bomchild` business order list**

```python
    "eng_bomchild": [
        "FID",
        "FENTRYID",
        "FSEQ",
        "FMASTERID",
        "FMATERIALID",
        "FCHILDNUMBER",
        "FCHILDNAME",
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
git commit -m "feat: order eng_bomchild child name column"
```

### Task 3: Align the SQL Server staging branch with FCHILDNAME

**Files:**
- Modify: `D:\Kingdee\tests\test_upsert_engine_sqlserver.py`
- Modify: `D:\Kingdee\src\core\upsert_engine_sqlserver.py`

- [ ] **Step 1: Update the staging test first so it fails on the missing child name**

```python
    def test_eng_bomchild_staging_sql_includes_child_number_and_name(self) -> None:
        manager = FakeSqlServerManager()
        manager.config["force_staging_tables"] = "eng_bomchild"
        manager.cursor._fetchone_queue = [(1,)]
        manager.cursor._fetchall_queue = [[]]
        manager._parse_insert_sql = lambda sql: (
            "eng_bomchild",
            [
                "FID",
                "FENTRYID",
                "FSEQ",
                "FMATERIALID",
                "FCHILDNUMBER",
                "FCHILDNAME",
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
            "FCHILDNAME": "nvarchar",
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
        }
        manager._get_primary_key = lambda table: "FID,FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql=(
                "INSERT INTO eng_bomchild (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, "
                "FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, "
                "FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            values=[[10, 1001, 1, "MAT-001", "CHILD-001", "子项名称", 2, 1, "1", "2", 200, 300, "ROW-1", 0, 5, 4, 900, "1", "2026-04-24 10:00:00"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        staging_sql = manager.cursor.executemany_calls[0][0]
        self.assertIn("FCHILDNUMBER, FCHILDNAME, FNUMERATOR", staging_sql)
        self.assertRegex(
            staging_sql,
            (
                r"TRY_CAST\(\? AS NVARCHAR\(64\)\),\s*"
                r"TRY_CAST\(\? AS NVARCHAR\(255\)\),\s*"
                r"TRY_CAST\(\? AS NVARCHAR\(255\)\),\s*"
                r"COALESCE\(TRY_CAST\(\? AS DECIMAL\(23,10\)\), 0\)"
            ),
        )
```

- [ ] **Step 2: Run the new staging test and verify it fails**

Run:

```powershell
python -m unittest tests.test_upsert_engine_sqlserver.UpsertEngineSqlServerTests.test_eng_bomchild_staging_sql_includes_child_number_and_name -v
```

Expected: `FAIL` because the hard-coded `eng_bomchild` staging SQL still omits `FCHILDNAME`.

- [ ] **Step 3: Add `FCHILDNAME` to the hard-coded `eng_bomchild` staging SQL**

```python
                            elif base_name.strip().lower() == "eng_bomchild":
                                insert_stage_sql = (
                                    f"INSERT INTO {stage_ref} (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, "
                                    f"FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE) "
                                    f"SELECT "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS INT), "
                                    f"TRY_CAST(? AS NVARCHAR(64)), "
                                    f"TRY_CAST(? AS NVARCHAR(255)), "
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

- [ ] **Step 4: Re-run the staging test and verify it passes**

Run:

```powershell
python -m unittest tests.test_upsert_engine_sqlserver.UpsertEngineSqlServerTests.test_eng_bomchild_staging_sql_includes_child_number_and_name -v
```

Expected: `OK`

- [ ] **Step 5: Commit**

```powershell
git add tests/test_upsert_engine_sqlserver.py src/core/upsert_engine_sqlserver.py
git commit -m "fix: align eng_bomchild staging with child name"
```

### Task 4: Run integrated tests, create the live column, and reorder SQL Server

**Files:**
- Reference: `D:\Kingdee\docs\superpowers\specs\2026-04-24-eng-bomchild-fchildname-design.md`
- Reference: `D:\Kingdee\scripts\reorder_sqlserver_business_tables.py`

- [ ] **Step 1: Run the full related test set**

Run:

```powershell
python -m unittest tests.test_eng_bomchild_field_mapping tests.test_sqlserver_business_layout tests.test_upsert_engine_sqlserver -v
```

Expected: `OK`

- [ ] **Step 2: Create the live SQL Server column through the repo’s manager**

Run:

```powershell
@'
from src.core.mysql_manager import mysql_manager

if not mysql_manager.connection or not mysql_manager.cursor:
    if not mysql_manager.connect():
        raise SystemExit("connect failed")

mysql_manager._ensure_additional_columns_for_eng_bomchild()
print(mysql_manager._table_has_column("eng_bomchild", "FCHILDNAME"))
'@ | python -
```

Expected: `True`

- [ ] **Step 3: Verify the live SQL Server table really has `FCHILDNAME`**

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
    ("eng_bomchild", "FCHILDNAME"),
)
print(mysql_manager.cursor.fetchall())
'@ | python -
```

Expected: one row containing `FCHILDNAME` and `nvarchar`

- [ ] **Step 4: Run the SQL Server reorder dry-run**

Run:

```powershell
python scripts/reorder_sqlserver_business_tables.py --tables eng_bomchild
```

Expected: output contains `desired:` with `FMATERIALID, FCHILDNUMBER, FCHILDNAME, FMATERIALTYPE`

- [ ] **Step 5: Execute the actual reorder**

Run:

```powershell
python scripts/reorder_sqlserver_business_tables.py --execute --tables eng_bomchild
```

Expected: output ends with `applied: eng_bomchild`

- [ ] **Step 6: Verify the material block order in SQL Server**

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
      AND COLUMN_NAME IN ('FMATERIALID', 'FCHILDNUMBER', 'FCHILDNAME', 'FMATERIALTYPE')
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
('FCHILDNAME', <n+2>)
('FMATERIALTYPE', <n+3>)
```

### Task 5: Backfill FCHILDNAME through a safe full sync and verify data landed

**Files:**
- Reference: `D:\Kingdee\main.py`
- Reference: `D:\Kingdee\src\core\filter_builder.py`

- [ ] **Step 1: Run a safe full sync for `物料清单子项`**

Run:

```powershell
python main.py sync --tables 物料清单子项 --mode full
```

Expected: CLI reports `status: success` and does not truncate `eng_bomchild`

- [ ] **Step 2: Verify `FCHILDNAME` is populated**

Run:

```powershell
@'
from src.core.mysql_manager import mysql_manager

if not mysql_manager.connection or not mysql_manager.cursor:
    if not mysql_manager.connect():
        raise SystemExit("connect failed")

mysql_manager.cursor.execute(
    """
    SELECT COUNT(1),
           SUM(CASE WHEN FCHILDNAME IS NOT NULL AND LTRIM(RTRIM(FCHILDNAME)) <> '' THEN 1 ELSE 0 END)
    FROM eng_bomchild
    """
)
print(mysql_manager.cursor.fetchall())
'@ | python -
```

Expected: second number is greater than `0`

- [ ] **Step 3: Sample a few rows to verify the new field looks reasonable**

Run:

```powershell
@'
from src.core.mysql_manager import mysql_manager

if not mysql_manager.connection or not mysql_manager.cursor:
    if not mysql_manager.connect():
        raise SystemExit("connect failed")

mysql_manager.cursor.execute(
    """
    SELECT TOP 10 FID, FENTRYID, FMATERIALID, FCHILDNUMBER, FCHILDNAME
    FROM eng_bomchild
    WHERE FCHILDNAME IS NOT NULL AND LTRIM(RTRIM(FCHILDNAME)) <> ''
    ORDER BY FMODIFYDATE DESC, FID DESC, FENTRYID DESC
    """
)
for row in mysql_manager.cursor.fetchall():
    print(row)
'@ | python -
```

Expected: sample rows contain non-empty `FCHILDNAME`

- [ ] **Step 4: Note the expected SQL Server logging change**

Checklist:

```text
[x] First sync can log that eng_bomchild.FCHILDNAME was created
[x] Later syncs should not log missing-column ignore warnings for FCHILDNAME
[x] Full sync is used for safe backfill; complete/reset is not required
```
