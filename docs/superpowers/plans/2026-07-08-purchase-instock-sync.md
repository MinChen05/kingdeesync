---
change: add-purchase-instock-sync
design-doc: docs/superpowers/specs/2026-07-07-purchase-instock-sync-design.md
base-ref: 850dae0d84e7967ed42008eec5ea9a4e2b779949
archived-with: 2026-07-08-add-purchase-instock-sync
---

# Purchase Instock Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增“采购入库单”基础明细同步，复用现有配置、writer registry、SQL Server staging/upsert 链路完成金蝶到 SQL Server 的幂等写入。

**Architecture:** 通过 `form-queries.json` 注册金蝶 `STK_InStock` 查询，通过 `tables.json` 注册目标表和 `insert_purchase_instock` writer，通过 `MySQLManager._prepare_purchase_instock_data` 做字段转换与无效行跳过。SQL Server 写入继续走 `_batch_insert`、`UpsertEngineSqlServer` 和 staging 配置，按分录级 `FENTRYID` 幂等。

**Tech Stack:** Python、unittest/pytest、JSON 配置、SQL Server upsert/staging、OpenSpec/Comet。

archived-with: 2026-07-08-add-purchase-instock-sync
---

## File Structure

- Modify: `src/config/form-queries.json`，新增“采购入库单”金蝶查询配置（原因：让同步入口能发现新表单）。
- Modify: `src/config/tables.json`，新增“采购入库单”目标表与 writer 映射（原因：让 `FormSyncRunner` 能解析写入目标）。
- Modify: `config.example.ini`，将目标表加入 `force_staging_tables`（原因：采购入库单属于 SQL Server 业务表批量写入，staging 更稳）。
- Modify: `src/core/sales_writer.py`，新增 `insert_purchase_instock`（原因：采购入库属于采购域，贴近采购订单和应付单 writer）。
- Modify: `src/core/writers_registry.py`，注册 `insert_purchase_instock`（原因：统一 writer 分发）。
- Modify: `src/core/mysql_manager.py`，新增 `insert_purchase_instock` 代理和 `_prepare_purchase_instock_data`（原因：沿用现有 manager + writer 组合模式）。
- Modify: `src/core/upsert_engine_sqlserver.py`，补充采购入库单 staging/upsert 主键过滤（原因：空分录主键必须跳过）。
- Modify: `src/tools/sqlserver_business_layout.py`，补充目标表列顺序和索引计划（原因：SQL Server 表结构和索引需可维护）。
- Test: `tests/test_config_manager.py`，覆盖内置配置注册。
- Test: `tests/test_writers_registry.py`，覆盖 writer 注册。
- Test: `tests/test_purchase_instock_write_validation.py`，覆盖字段准备和无效行跳过。
- Test: `tests/test_upsert_engine_sqlserver.py`，覆盖 SQL Server staging/upsert 主键行为。
- Test: `tests/test_sqlserver_business_layout.py`，覆盖目标表列顺序。

## Task 1: 配置注册

**Files:**
- Modify: `src/config/form-queries.json`
- Modify: `src/config/tables.json`
- Modify: `config.example.ini`
- Test: `tests/test_config_manager.py`

- [ ] **Step 1: 先写配置注册测试**

在 `tests/test_config_manager.py` 的 `ConfigManagerTests` 中新增：

```python
    def test_builtin_tables_json_registers_purchase_instock_sync(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tables = json.loads((repo_root / "src" / "config" / "tables.json").read_text(encoding="utf-8"))
        form_queries = json.loads((repo_root / "src" / "config" / "form-queries.json").read_text(encoding="utf-8"))

        self.assertIn("采购入库单", form_queries)
        self.assertEqual(form_queries["采购入库单"]["FormId"], "STK_InStock")
        self.assertIn("FID", form_queries["采购入库单"]["FieldKeys"].split(","))
        self.assertIn("FBillNo", form_queries["采购入库单"]["FieldKeys"].split(","))
        self.assertIn("FModifyDate", form_queries["采购入库单"]["FieldKeys"].split(","))
        self.assertIn("采购入库单", tables)
        self.assertEqual(tables["采购入库单"]["table"], "STK_InStock")
        self.assertEqual(tables["采购入库单"]["insert_method"], "insert_purchase_instock")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config_manager.py::ConfigManagerTests::test_builtin_tables_json_registers_purchase_instock_sync -q`

Expected: FAIL，断言“采购入库单”不存在。

- [ ] **Step 3: 新增内置查询配置**

在 `src/config/form-queries.json` 增加：

```json
  "采购入库单": {
    "FormId": "STK_InStock",
    "FieldKeys": "FID,FInStockEntry_FENTRYID,FInStockEntry_FSEQ,FBillNo,FDate,FDocumentStatus,FSupplierId.FNAME,FPurchaseOrgId.FNAME,FMaterialId.FNUMBER,FMaterialId.FNAME,FRealQty,FSrcBillNo,FSrcEntrySeq,FModifyDate",
    "FilterString": "FPurchaseOrgId = 171190",
    "OrderString": "",
    "TopRowCount": 0,
    "StartRow": 0,
    "Limit": 0,
    "SubSystemId": ""
  }
```

字段 dry-run 后可校准；当前先覆盖基础明细（原因：用户选择 A 方案）。

- [ ] **Step 4: 新增目标表映射**

在 `src/config/tables.json` 增加：

```json
    "采购入库单":         { "table": "STK_InStock",          "insert_method": "insert_purchase_instock" }
```

- [ ] **Step 5: 新增 staging 配置**

在 `config.example.ini` 的 `force_staging_tables` 中追加 `stk_instock` 或 `STK_InStock`，保持最终目标表名一致。

- [ ] **Step 6: 运行配置测试**

Run: `python -m pytest tests/test_config_manager.py::ConfigManagerTests::test_builtin_tables_json_registers_purchase_instock_sync -q`

Expected: PASS。

- [ ] **Step 7: 提交配置任务**

```bash
git add src/config/form-queries.json src/config/tables.json config.example.ini tests/test_config_manager.py
git commit -m "feat: register purchase instock sync config"
```

## Task 2: Writer 注册

**Files:**
- Modify: `src/core/sales_writer.py`
- Modify: `src/core/writers_registry.py`
- Test: `tests/test_writers_registry.py`

- [ ] **Step 1: 先写 writer 注册测试**

在 `tests/test_writers_registry.py` 增加：

```python
    def test_purchase_instock_writer_is_registered(self) -> None:
        registry = WriterRegistry()
        self.assertTrue(registry.has("insert_purchase_instock"))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_writers_registry.py::WriterRegistryTests::test_purchase_instock_writer_is_registered -q`

Expected: FAIL，`insert_purchase_instock` 未注册。

- [ ] **Step 3: 新增 writer 函数**

在 `src/core/sales_writer.py` 采购订单 writer 附近新增：

```python
def insert_purchase_instock(manager, data: List[Dict]) -> int:
        """插入采购入库单数据（STK_InStock）"""
        if not data:
            return 0

        sql = """
            INSERT INTO STK_InStock (
                FID, FENTRYID, FSEQ, FBILLNO, FDATE, FDOCUMENTSTATUS,
                FSUPPLIERNAME, FPURCHASEORGNAME, FMATERIALNUMBER, FMATERIALNAME,
                FREALQTY, FSRCBILLNO, FSRCENTRYSEQ, FModifyDate
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                FID=VALUES(FID),
                FSEQ=VALUES(FSEQ),
                FBILLNO=VALUES(FBILLNO),
                FDATE=VALUES(FDATE),
                FDOCUMENTSTATUS=VALUES(FDOCUMENTSTATUS),
                FSUPPLIERNAME=VALUES(FSUPPLIERNAME),
                FPURCHASEORGNAME=VALUES(FPURCHASEORGNAME),
                FMATERIALNUMBER=VALUES(FMATERIALNUMBER),
                FMATERIALNAME=VALUES(FMATERIALNAME),
                FREALQTY=VALUES(FREALQTY),
                FSRCBILLNO=VALUES(FSRCBILLNO),
                FSRCENTRYSEQ=VALUES(FSRCENTRYSEQ),
                FModifyDate=VALUES(FModifyDate),
                SYNC_TIME=CURRENT_TIMESTAMP
            """
        return manager._batch_insert(sql, data, manager._prepare_purchase_instock_data)
```

- [ ] **Step 4: 注册 writer**

在 `src/core/writers_registry.py` 的 `from src.core.sales_writer import (...)` 增加 `insert_purchase_instock`，并在 `WRITER_REGISTRY` 增加：

```python
    "insert_purchase_instock": insert_purchase_instock,
```

- [ ] **Step 5: 运行 writer 注册测试**

Run: `python -m pytest tests/test_writers_registry.py::WriterRegistryTests::test_purchase_instock_writer_is_registered -q`

Expected: PASS。

- [ ] **Step 6: 提交 writer 注册任务**

```bash
git add src/core/sales_writer.py src/core/writers_registry.py tests/test_writers_registry.py
git commit -m "feat: register purchase instock writer"
```

## Task 3: 字段准备与无效行跳过

**Files:**
- Modify: `src/core/mysql_manager.py`
- Test: `tests/test_purchase_instock_write_validation.py`

- [ ] **Step 1: 新增字段准备测试文件**

Create `tests/test_purchase_instock_write_validation.py`:

```python
from __future__ import annotations

import unittest

from src.core.mysql_manager import MySQLManager
from src.core.write_outcome import WriteOutcome


class PurchaseInstockPrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MySQLManager.__new__(MySQLManager)
        self.manager._last_write_outcome = WriteOutcome()

    def test_prepare_purchase_instock_data_maps_basic_fields(self) -> None:
        row = {
            "FID": 10,
            "FInStockEntry_FENTRYID": 1001,
            "FInStockEntry_FSEQ": 1,
            "FBillNo": "PI20260708001",
            "FDate": "2026-07-08 08:00:00",
            "FDocumentStatus": "C",
            "FSupplierId.FNAME": "供应商A",
            "FPurchaseOrgId.FNAME": "台州市金宇机电有限公司",
            "FMaterialId.FNUMBER": "MAT-001",
            "FMaterialId.FNAME": "电机",
            "FRealQty": "12.5",
            "FSrcBillNo": "PO20260701001",
            "FSrcEntrySeq": 2,
            "FModifyDate": "2026-07-08 09:00:00",
        }

        prepared = MySQLManager._prepare_purchase_instock_data(self.manager, row)

        self.assertEqual(prepared[0], 10)
        self.assertEqual(prepared[1], 1001)
        self.assertEqual(prepared[3], "PI20260708001")
        self.assertEqual(prepared[6], "供应商A")
        self.assertEqual(prepared[10], 12.5)

    def test_prepare_purchase_instock_data_skips_blank_entry_id(self) -> None:
        row = {"FID": 10, "FInStockEntry_FENTRYID": "", "FBillNo": "PI20260708001"}

        prepared = MySQLManager._prepare_purchase_instock_data(self.manager, row)

        self.assertIsNone(prepared)
        self.assertEqual(self.manager._last_write_outcome.invalid, 1)

    def test_prepare_purchase_instock_data_skips_blank_billno(self) -> None:
        row = {"FID": 10, "FInStockEntry_FENTRYID": 1001, "FBillNo": "   "}

        prepared = MySQLManager._prepare_purchase_instock_data(self.manager, row)

        self.assertIsNone(prepared)
        self.assertEqual(self.manager._last_write_outcome.invalid, 1)

    def test_prepare_purchase_instock_data_accepts_uppercase_aliases(self) -> None:
        row = {"FID": 10, "FENTRYID": 1001, "FBILLNO": "PI20260708001"}

        prepared = MySQLManager._prepare_purchase_instock_data(self.manager, row)

        self.assertEqual(prepared[1], 1001)
        self.assertEqual(prepared[3], "PI20260708001")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_purchase_instock_write_validation.py -q`

Expected: FAIL，`_prepare_purchase_instock_data` 不存在。

- [ ] **Step 3: 新增 manager 代理方法**

在 `src/core/mysql_manager.py` 的 `insert_ap_payable` 附近新增：

```python
    def insert_purchase_instock(self, data: list[dict]) -> int:
        return self.execute_writer("insert_purchase_instock", data)
```

- [ ] **Step 4: 新增字段准备方法**

在 `src/core/mysql_manager.py` 的 `_prepare_purchase_order_data` 附近新增：

```python
    def _prepare_purchase_instock_data(self, item) -> tuple | None:
        """准备采购入库单基础明细数据。"""
        try:
            if isinstance(item, dict):
                fid = self._to_int_or_none(item.get("FID"))
                fentryid = self._to_int_or_none(
                    item.get("FInStockEntry_FENTRYID")
                    or item.get("FEntity_FENTRYID")
                    or item.get("FENTRYID")
                )
                fbillno = self._safe_str(item.get("FBillNo") or item.get("FBILLNO"))

                if fid is None or fentryid is None:
                    self._record_invalid_row()
                    logger.warning(
                        "采购入库单主键为空，已跳过: FID=%s FENTRYID=%s FBILLNO=%s",
                        item.get("FID"),
                        item.get("FInStockEntry_FENTRYID") or item.get("FENTRYID"),
                        fbillno,
                    )
                    return None
                if not fbillno:
                    self._record_invalid_row()
                    logger.warning("采购入库单单号为空，已跳过: FID=%s FENTRYID=%s", fid, fentryid)
                    return None

                return (
                    fid,
                    fentryid,
                    self._to_int_or_none(item.get("FInStockEntry_FSEQ") or item.get("FSEQ")),
                    fbillno,
                    self._parse_datetime(item.get("FDate") or item.get("FDATE")),
                    self._safe_str(item.get("FDocumentStatus") or item.get("FDOCUMENTSTATUS")),
                    self._safe_str(item.get("FSupplierId.FNAME") or item.get("FSUPPLIERID.FNAME")),
                    self._safe_str(item.get("FPurchaseOrgId.FNAME") or item.get("FPURCHASEORGID.FNAME")),
                    self._safe_str(item.get("FMaterialId.FNUMBER") or item.get("FMATERIALID.FNUMBER")),
                    self._safe_str(item.get("FMaterialId.FNAME") or item.get("FMATERIALID.FNAME")),
                    self._to_decimal_or_none(item.get("FRealQty") or item.get("FREALQTY")) or 0,
                    self._safe_str(item.get("FSrcBillNo") or item.get("FSRCBILLNO")),
                    self._to_int_or_none(item.get("FSrcEntrySeq") or item.get("FSRCENTRYSEQ")),
                    self._parse_datetime(item.get("FModifyDate") or item.get("FMODIFYDATE")),
                )
            return None
        except Exception as e:
            logger.error(f"准备采购入库单数据失败: {str(e)}")
            self._record_invalid_row()
            return None
```

如本地 helper 名称不是 `_to_decimal_or_none`，改用现有等价数值转换 helper（原因：必须基于实际 `mysql_manager.py` 中存在的方法）。

- [ ] **Step 5: 运行字段准备测试**

Run: `python -m pytest tests/test_purchase_instock_write_validation.py -q`

Expected: PASS。

- [ ] **Step 6: 提交字段准备任务**

```bash
git add src/core/mysql_manager.py tests/test_purchase_instock_write_validation.py
git commit -m "feat: prepare purchase instock rows"
```

## Task 4: SQL Server 幂等与表结构支持

**Files:**
- Modify: `src/core/mysql_manager.py`
- Modify: `src/core/upsert_engine_sqlserver.py`
- Modify: `src/tools/sqlserver_business_layout.py`
- Test: `tests/test_upsert_engine_sqlserver.py`
- Test: `tests/test_sqlserver_business_layout.py`

- [ ] **Step 1: 写 upsert 主键测试**

在 `tests/test_upsert_engine_sqlserver.py` 增加：

```python
    def test_stk_instock_filters_missing_entryid(self) -> None:
        manager = FakeSqlServerManager()
        manager.cursor._fetchall_queue = [
            [
                ("FID", "bigint", None),
                ("FENTRYID", "bigint", None),
                ("FSEQ", "int", None),
                ("FBILLNO", "nvarchar", 80),
                ("SYNC_TIME", "datetime", None),
            ],
            [],
        ]
        manager._parse_insert_sql = lambda sql: ("STK_InStock", ["FID", "FENTRYID", "FSEQ", "FBILLNO"])
        manager._get_table_columns_info = lambda table: {
            "FID": "bigint",
            "FENTRYID": "bigint",
            "FSEQ": "int",
            "FBILLNO": "nvarchar",
            "SYNC_TIME": "datetime",
        }
        manager._get_primary_key = lambda table: "FENTRYID"
        engine = UpsertEngineSqlServer(manager)

        inserted = engine.execute(
            sql="INSERT INTO STK_InStock (FID, FENTRYID, FSEQ, FBILLNO) VALUES (%s, %s, %s, %s)",
            values=[[10, None, 1, "PI20260708001"], [10, 1001, 1, "PI20260708001"]],
            batch_size=10000,
            commit_every_n_batches=0,
        )

        self.assertEqual(inserted, 1)
        self.assertEqual(len(manager.cursor.executemany_calls[0][1]), 1)
```

- [ ] **Step 2: 写列顺序测试**

在 `tests/test_sqlserver_business_layout.py` 增加：

```python
    def test_stk_instock_places_material_and_source_fields_before_modifydate(self) -> None:
        existing = [
            "FID", "FENTRYID", "FSEQ", "FBILLNO", "FDATE", "FDOCUMENTSTATUS",
            "FMODIFYDATE", "SYNC_TIME", "FSUPPLIERNAME", "FPURCHASEORGNAME",
            "FMATERIALNUMBER", "FMATERIALNAME", "FREALQTY", "FSRCBILLNO", "FSRCENTRYSEQ",
        ]

        ordered = resolve_desired_order("STK_InStock", existing)

        self.assertEqual(
            ordered,
            [
                "FID", "FENTRYID", "FSEQ", "FBILLNO", "FDATE", "FDOCUMENTSTATUS",
                "FSUPPLIERNAME", "FPURCHASEORGNAME", "FMATERIALNUMBER", "FMATERIALNAME",
                "FREALQTY", "FSRCBILLNO", "FSRCENTRYSEQ", "FMODIFYDATE", "SYNC_TIME",
            ],
        )
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_upsert_engine_sqlserver.py::UpsertEngineSqlServerTests::test_stk_instock_filters_missing_entryid tests/test_sqlserver_business_layout.py::SqlServerBusinessLayoutTests::test_stk_instock_places_material_and_source_fields_before_modifydate -q`

Expected: 至少列顺序测试失败，upsert 可能因已有通用逻辑通过；失败点用于驱动实现。

- [ ] **Step 4: 补充主键映射**

在 `src/core/mysql_manager.py` 的 `_get_primary_key` 映射中增加：

```python
            "stk_instock": "FENTRYID",
```

如目标表最终保持大小写 `STK_InStock`，该方法会 normalize 表名时仍应匹配小写 key。

- [ ] **Step 5: 补充 upsert 特殊过滤**

在 `src/core/upsert_engine_sqlserver.py` 中参照 `prd_instock` / `ar_receivable` 现有逻辑，确保 `STK_InStock` 使用 `FENTRYID` 过滤空主键。优先复用通用主键过滤；只有现有逻辑无法覆盖时才添加 `base_name.strip().lower() == "stk_instock"` 分支（原因：减少表单特判）。

- [ ] **Step 6: 补充业务列顺序和索引计划**

在 `src/tools/sqlserver_business_layout.py` 中增加 `STK_InStock` 或 normalize 后的 `stk_instock` 列顺序：

```python
    "stk_instock": [
        "FID", "FENTRYID", "FSEQ", "FBILLNO", "FDATE", "FDOCUMENTSTATUS",
        "FSUPPLIERNAME", "FPURCHASEORGNAME", "FMATERIALNUMBER", "FMATERIALNAME",
        "FREALQTY", "FSRCBILLNO", "FSRCENTRYSEQ", "FMODIFYDATE", "SYNC_TIME",
    ],
```

并在索引计划中增加：

```python
    "stk_instock": [IndexPlan("UX_STK_InStock_fentryid", ("FENTRYID",), unique=True, clustered=False)],
```

- [ ] **Step 7: 运行 SQL Server 相关测试**

Run: `python -m pytest tests/test_upsert_engine_sqlserver.py::UpsertEngineSqlServerTests::test_stk_instock_filters_missing_entryid tests/test_sqlserver_business_layout.py::SqlServerBusinessLayoutTests::test_stk_instock_places_material_and_source_fields_before_modifydate -q`

Expected: PASS。

- [ ] **Step 8: 提交 SQL Server 支持任务**

```bash
git add src/core/mysql_manager.py src/core/upsert_engine_sqlserver.py src/tools/sqlserver_business_layout.py tests/test_upsert_engine_sqlserver.py tests/test_sqlserver_business_layout.py
git commit -m "feat: support purchase instock sqlserver upsert"
```

## Task 5: 既有未提交改动核验

**Files:**
- Inspect: `assets/styles.css`
- Inspect: `src/core/mysql_manager.py`
- Inspect: `check_latest2.py`
- Inspect: `check_latest3.py`
- Inspect: `check_latest4.py`
- Inspect: `check_latest_error.py`
- Inspect: `docs/screenshots/log_center_*.png`

- [ ] **Step 1: 记录 dirty worktree 归因**

Run:

```bash
git diff --stat
git ls-files --others --exclude-standard
```

Expected: 输出包含用户已确认并入当前 change 的既有改动。

- [ ] **Step 2: 复核 `src/core/mysql_manager.py` 改动不被覆盖**

Run:

```bash
git diff -- src/core/mysql_manager.py
```

Expected: 能看到既有改动和本次新增采购入库单方法同时存在；不得回滚用户已有内容。

- [ ] **Step 3: 复核非运行时文件影响**

Run:

```bash
git status --short docs/screenshots check_latest2.py check_latest3.py check_latest4.py check_latest_error.py assets/styles.css
```

Expected: 截图、诊断脚本、样式改动仍保留；在最终验证报告说明它们属于并入范围但不影响采购入库单 writer 运行路径。

- [ ] **Step 4: 提交归因记录**

如仅需文档记录，在 `openspec/changes/add-purchase-instock-sync/tasks.md` 对 5.1-5.3 勾选时一并提交；不要删除或回滚这些文件（原因：用户明确要求并入当前 change）。

```bash
git add openspec/changes/add-purchase-instock-sync/tasks.md
git commit -m "docs: record purchase instock dirty worktree review"
```

## Task 6: 回归验证与 OpenSpec 校验

**Files:**
- Modify: `openspec/changes/add-purchase-instock-sync/tasks.md`

- [ ] **Step 1: 运行采购入库单专项测试**

Run:

```bash
python -m pytest tests/test_config_manager.py::ConfigManagerTests::test_builtin_tables_json_registers_purchase_instock_sync tests/test_writers_registry.py::WriterRegistryTests::test_purchase_instock_writer_is_registered tests/test_purchase_instock_write_validation.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行 SQL Server 相关回归测试**

Run:

```bash
python -m pytest tests/test_upsert_engine_sqlserver.py tests/test_sqlserver_business_layout.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行相邻表单回归测试**

Run:

```bash
python -m pytest tests/test_prd_instock_write_validation.py tests/test_ap_payable_field_mapping.py tests/test_writers_registry.py -q
```

Expected: PASS。

- [ ] **Step 4: 运行 OpenSpec 严格校验**

Run:

```bash
openspec validate add-purchase-instock-sync --strict
```

Expected: `Change 'add-purchase-instock-sync' is valid`。

- [ ] **Step 5: 记录 SQL Server 写入日志预期**

在最终验证报告中说明：采购入库单 dry-run 应显示 `STK_InStock` 查询字段、分页拉取数量、跳过无效主键/单号记录数量、staging/upsert 目标表和写入/更新行数（原因：本轮不直接清空或破坏生产数据）。

- [ ] **Step 6: 勾选 OpenSpec tasks 并提交**

完成实现与验证后，将 `openspec/changes/add-purchase-instock-sync/tasks.md` 对应任务从 `- [ ]` 改为 `- [x]`，再提交：

```bash
git add openspec/changes/add-purchase-instock-sync/tasks.md
git commit -m "docs: complete purchase instock sync tasks"
```

## Self-Review

- Spec coverage: 覆盖“采购入库单可配置同步”“基础明细字段”“分录级幂等写入”“无效记录处理”“SQL Server 写入验证”五项要求。
- Placeholder scan: 无 TBD/TODO/稍后实现等占位步骤。
- Type consistency: writer 名称统一为 `insert_purchase_instock`，目标表统一为 `STK_InStock`，主键统一为 `FENTRYID`。
