# P1 Field Mapping And Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地研发优化路线图的 `P1` 波次（`3 全局字段映射配置文件`、`2 字段截断自动适配`、`7 断点续传覆盖更多失败场景`），把字段适配与恢复语义收敛成可复用能力。

**Architecture:** 在现有 `tables.json` / `form-queries.json` 旁新增 `field_mappings.json` 作为字段适配规则源，并用一个小型 `field_mapping_resolver` 负责 source alias、默认值、类型转换、最大长度策略。`mysql_manager.py` 里的 selected prepare 路径逐步改为“配置驱动 + 诊断兜底”。断点层不做新存储，而是在现有 `SyncCheckpoint` 上扩展“下一页游标 + 已成功写入记录标识”，由 `FormSyncRunner` 在每次成功写入后持久化。

**Tech Stack:** Python 3.11, unittest, JSON config files, existing `CheckpointManager`, SQL Server/MySQL compatible prepare functions

---

## File Structure

**Create**

- `src/config/field_mappings.json`
- `src/core/field_mapping_resolver.py`
- `tests/test_field_mapping_resolver.py`
- `tests/test_sync_checkpoint_resume.py`

**Modify**

- `src/config/config_accessors.py`
- `src/config/config_manager.py`
- `src/core/mysql_manager.py`
- `src/core/retry_manager.py`
- `src/core/form_sync_runner.py`
- `tests/test_prd_mo_cancel_status.py`
- `tests/test_ap_payable_field_mapping.py`
- `tests/test_eng_bomchild_field_mapping.py`
- `tests/test_form_sync_runner.py`
- `tests/test_upsert_engine_sqlserver.py`

## Scope Guard

这个 plan **只覆盖 P1**：

- `3 全局字段映射配置文件`
- `2 字段截断自动适配`
- `7 断点续传覆盖更多失败场景`

明确不做：

- `P0` 的失败明细、熔断、任务级 metrics 落盘扩展
- `P2` 的会话预热、分页并发、批次策略
- 新数据库表或新持久化机制

## Design Decisions

### 1. 字段映射规则文件单独于 `tables.json`

原因：

- `tables.json` 当前只负责“表单 -> 目标表 / writer”
- 字段映射规则粒度更细，独立文件更可控

### 2. 截断适配优先做“预写入规则处理”，不做异常后盲重试

原因：

- `mysql_manager.py` 已经有 `_diagnose_string_truncation()`，但那是诊断，不是稳定行为
- `P1` 要把规则前移到 prepare 阶段，避免写库前后口径分裂

### 3. 断点恢复语义升级为“下一页游标 + 最近成功写入标识”

原因：

- 当前 `SyncCheckpoint.start_row` 只在查询失败重试时保存
- `P1` 要覆盖“已经写入部分页后进程异常退出”的场景
- 不引入新存储，继续复用 checkpoint JSON

### 4. P1 首批只迁移 3 条代表路径

先迁移以下 prepare 路径：

- `prd_mo` 的 `FCANCELSTATUS`
- `ap_payable` 的 `FNOTAXAMOUNTFOR`
- `eng_bomchild` 的 `FCHILDNUMBER` / `FCHILDNAME`

原因：

- 都有现成测试与已知差异点
- 这三条能覆盖字符串默认值、数值 source alias、多字段映射三种典型模式

### Task 1: 为字段映射配置与解析器写红灯测试

**Files:**
- Create: `tests/test_field_mapping_resolver.py`
- Modify: `tests/test_prd_mo_cancel_status.py`
- Modify: `tests/test_ap_payable_field_mapping.py`
- Modify: `tests/test_eng_bomchild_field_mapping.py`

- [ ] **Step 1: 新建解析器测试文件**

```python
from __future__ import annotations

import unittest

from src.core.field_mapping_resolver import FieldMappingResolver


class FieldMappingResolverTests(unittest.TestCase):
    def test_resolve_prefers_first_present_source_alias(self) -> None:
        resolver = FieldMappingResolver(
            {
                "ap_payable": {
                    "FNOTAXAMOUNTFOR": {
                        "sources": ["FNoTaxAmountFor_D", "FNOTAXAMOUNTFOR_D"],
                        "type": "decimal",
                        "default": 0.0,
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            {"FNOTAXAMOUNTFOR_D": "100.50"},
        )

        self.assertEqual(result, 100.5)

    def test_resolve_uses_default_when_all_sources_are_missing(self) -> None:
        resolver = FieldMappingResolver(
            {
                "prd_mo": {
                    "FCANCELSTATUS": {
                        "sources": ["FCANCELSTATUS", "FCancelStatus"],
                        "type": "string",
                        "default": "",
                    }
                }
            }
        )

        result = resolver.resolve_field("prd_mo", "FCANCELSTATUS", {})

        self.assertEqual(result, "")

    def test_resolve_trims_string_by_max_length_when_policy_is_trim(self) -> None:
        resolver = FieldMappingResolver(
            {
                "eng_bomchild": {
                    "FCHILDNAME": {
                        "sources": ["FMATERIALIDCHILD.FNAME", "FCHILDNAME"],
                        "type": "string",
                        "default": "",
                        "max_length": 5,
                        "truncate_policy": "trim",
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "eng_bomchild",
            "FCHILDNAME",
            {"FCHILDNAME": "ABCDEFG"},
        )

        self.assertEqual(result, "ABCDE")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 扩展已有字段映射测试，让 prepare 路径依赖 resolver**

```python
    def test_prepare_ap_payable_data_prefers_mapping_alias_value(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.field_mapping_resolver = Mock()
        manager.field_mapping_resolver.resolve_field.side_effect = lambda table, field, row: 100.0

        prepared = manager._prepare_ap_payable_data(
            {
                "FID": 1001,
                "FEntityDetail_FENTRYID": 2001,
                "FEntityDetail_FSEQ": 1,
                "FBillNo": "AP202601001",
            }
        )

        self.assertEqual(prepared[15], 100.0)
        manager.field_mapping_resolver.resolve_field.assert_any_call(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            unittest.mock.ANY,
        )
```

- [ ] **Step 3: 运行红灯测试**

Run: `python -m unittest tests.test_field_mapping_resolver tests.test_prd_mo_cancel_status tests.test_ap_payable_field_mapping tests.test_eng_bomchild_field_mapping -v`

Expected:
- `ModuleNotFoundError: src.core.field_mapping_resolver`
- 现有 prepare 测试因 `field_mapping_resolver` 尚未接入而失败

- [ ] **Step 4: 提交红灯测试**

```bash
git add tests/test_field_mapping_resolver.py tests/test_prd_mo_cancel_status.py tests/test_ap_payable_field_mapping.py tests/test_eng_bomchild_field_mapping.py
git commit -m "test: cover p1 field mapping resolver"
```

### Task 2: 新增 `field_mappings.json` 与解析器实现

**Files:**
- Create: `src/config/field_mappings.json`
- Create: `src/core/field_mapping_resolver.py`
- Modify: `src/config/config_accessors.py`
- Modify: `src/config/config_manager.py`
- Test: `tests/test_field_mapping_resolver.py`

- [ ] **Step 1: 新建最小字段映射配置文件**

```json
{
  "prd_mo": {
    "FCANCELSTATUS": {
      "sources": ["FCANCELSTATUS", "FCancelStatus"],
      "type": "string",
      "default": "",
      "truncate_policy": "reject"
    }
  },
  "ap_payable": {
    "FNOTAXAMOUNTFOR": {
      "sources": ["FNoTaxAmountFor_D", "FNOTAXAMOUNTFOR_D"],
      "type": "decimal",
      "default": 0.0
    }
  },
  "eng_bomchild": {
    "FCHILDNUMBER": {
      "sources": ["FMATERIALIDCHILD.FNUMBER", "FMATERIALIDCHILD.FNumber", "FCHILDNUMBER"],
      "type": "string",
      "default": ""
    },
    "FCHILDNAME": {
      "sources": ["FMATERIALIDCHILD.FNAME", "FMATERIALIDCHILD.FName", "FCHILDNAME"],
      "type": "string",
      "default": "",
      "max_length": 255,
      "truncate_policy": "trim"
    }
  }
}
```

- [ ] **Step 2: 实现解析器**

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(slots=True)
class FieldMappingRule:
    sources: list[str]
    type: str = "string"
    default: Any = None
    max_length: int | None = None
    truncate_policy: str = "reject"


class FieldMappingResolver:
    def __init__(self, mapping_data: dict[str, dict[str, dict[str, Any]]]) -> None:
        self.mapping_data = mapping_data

    def get_rule(self, table_name: str, field_name: str) -> FieldMappingRule | None:
        table_rules = self.mapping_data.get(table_name, {})
        rule = table_rules.get(field_name)
        if not isinstance(rule, dict):
            return None
        return FieldMappingRule(
            sources=[str(source) for source in rule.get("sources", [])],
            type=str(rule.get("type", "string")),
            default=rule.get("default"),
            max_length=rule.get("max_length"),
            truncate_policy=str(rule.get("truncate_policy", "reject")),
        )

    def resolve_field(self, table_name: str, field_name: str, row: dict[str, Any]) -> Any:
        rule = self.get_rule(table_name, field_name)
        if rule is None:
            return row.get(field_name)

        raw_value = None
        for source in rule.sources:
            if source in row and row[source] not in (None, ""):
                raw_value = row[source]
                break

        value = rule.default if raw_value in (None, "") else raw_value
        if rule.type == "decimal":
            try:
                return float(Decimal(str(value)))
            except (InvalidOperation, ValueError, TypeError):
                return float(rule.default or 0.0)
        if rule.type == "int":
            try:
                return int(value)
            except Exception:
                return int(rule.default or 0)

        text = "" if value is None else str(value).strip()
        if rule.max_length and len(text) > rule.max_length:
            if rule.truncate_policy == "trim":
                return text[: rule.max_length]
            raise ValueError(f"{table_name}.{field_name} exceeds max_length={rule.max_length}")
        return text if text != "" else rule.default
```

- [ ] **Step 3: 在配置访问层暴露字段映射**

```python
def load_field_mappings_json(config_file: str, logger: logging.Logger) -> dict[str, dict[str, dict[str, Any]]]:
    config_dir = os.path.dirname(os.path.abspath(config_file))
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(config_dir, "field_mappings.json"),
        os.path.join(base_dir, "config", "field_mappings.json"),
    ]
    for file_path in candidates:
        try:
            if not os.path.exists(file_path):
                continue
            with open(file_path, encoding="utf-8") as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                return data
        except Exception as err:
            logger.warning("Failed to load field_mappings.json: %s - %s", file_path, err)
    return {}


class ConfigAccessors:
    def get_field_mappings(self) -> dict[str, dict[str, dict[str, Any]]]:
        return load_field_mappings_json(self.config_file, self.logger)
```

- [ ] **Step 4: 在 `ConfigManager` facade 暴露新接口**

```python
class ConfigManager:
    def get_field_mappings(self) -> dict[str, dict[str, dict[str, Any]]]:
        return self._accessors.get_field_mappings()
```

- [ ] **Step 5: 运行解析器测试转绿**

Run: `python -m unittest tests.test_field_mapping_resolver -v`

Expected: all tests `OK`

- [ ] **Step 6: 提交配置与解析器基础设施**

```bash
git add src/config/field_mappings.json src/core/field_mapping_resolver.py src/config/config_accessors.py src/config/config_manager.py tests/test_field_mapping_resolver.py
git commit -m "feat: add field mapping resolver"
```

### Task 3: 把已知字段差异迁移到配置驱动

**Files:**
- Modify: `src/core/mysql_manager.py`
- Modify: `tests/test_prd_mo_cancel_status.py`
- Modify: `tests/test_ap_payable_field_mapping.py`
- Modify: `tests/test_eng_bomchild_field_mapping.py`

- [ ] **Step 1: 在 `MySQLManager.reload_config()` 中挂载 resolver**

```python
from src.core.field_mapping_resolver import FieldMappingResolver


    def reload_config(self):
        ...
        self.field_mapping_resolver = FieldMappingResolver(config_manager.get_field_mappings())
        self._init_pool()
```

- [ ] **Step 2: 用 resolver 替换 `prd_mo` 的 `FCANCELSTATUS` 取值**

```python
    def _prepare_production_order_data(self, item) -> tuple | None:
        ...
        row = item if isinstance(item, dict) else {
            "FCANCELSTATUS": item[9] if len(item) > 9 else None,
            "FCancelStatus": item[9] if len(item) > 9 else None,
        }
        fcancel = self.field_mapping_resolver.resolve_field("prd_mo", "FCANCELSTATUS", row)
```

- [ ] **Step 3: 用 resolver 替换 `ap_payable` 的 `FNOTAXAMOUNTFOR` 取值**

```python
        row_map = item if isinstance(item, dict) else {}
        fnotaxamountfor = self.field_mapping_resolver.resolve_field(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            row_map,
        )
```

- [ ] **Step 4: 用 resolver 替换 `eng_bomchild` 的子项编号与名称**

```python
        row_map = item if isinstance(item, dict) else {}
        child_number = self.field_mapping_resolver.resolve_field(
            "eng_bomchild",
            "FCHILDNUMBER",
            row_map,
        )
        child_name = self.field_mapping_resolver.resolve_field(
            "eng_bomchild",
            "FCHILDNAME",
            row_map,
        )
```

- [ ] **Step 5: 跑字段映射回归**

Run: `python -m unittest tests.test_prd_mo_cancel_status tests.test_ap_payable_field_mapping tests.test_eng_bomchild_field_mapping -v`

Expected: all tests `OK`

- [ ] **Step 6: 提交配置驱动字段迁移**

```bash
git add src/core/mysql_manager.py tests/test_prd_mo_cancel_status.py tests/test_ap_payable_field_mapping.py tests/test_eng_bomchild_field_mapping.py
git commit -m "feat: apply config driven field mappings"
```

### Task 4: 为截断适配增加配置驱动策略

**Files:**
- Modify: `src/core/field_mapping_resolver.py`
- Modify: `src/config/field_mappings.json`
- Modify: `tests/test_field_mapping_resolver.py`
- Modify: `tests/test_upsert_engine_sqlserver.py`

- [ ] **Step 1: 为截断策略补红灯测试**

```python
    def test_resolve_raises_for_overflow_when_policy_is_reject(self) -> None:
        resolver = FieldMappingResolver(
            {
                "prd_mo": {
                    "FBILLNO": {
                        "sources": ["FBILLNO"],
                        "type": "string",
                        "default": "",
                        "max_length": 3,
                        "truncate_policy": "reject",
                    }
                }
            }
        )

        with self.assertRaisesRegex(ValueError, "prd_mo.FBILLNO exceeds max_length=3"):
            resolver.resolve_field("prd_mo", "FBILLNO", {"FBILLNO": "ABCDE"})
```

- [ ] **Step 2: 扩展配置文件，给可安全截断字段加 `max_length`**

```json
  "eng_bomchild": {
    "FCHILDNAME": {
      "sources": ["FMATERIALIDCHILD.FNAME", "FMATERIALIDCHILD.FName", "FCHILDNAME"],
      "type": "string",
      "default": "",
      "max_length": 255,
      "truncate_policy": "trim"
    }
  }
```

- [ ] **Step 3: 在 SQL Server 截断诊断测试中锁住“规则优先”**

```python
    def test_diagnose_string_truncation_keeps_rule_driven_trim_fields_out_of_failure_bucket(self) -> None:
        ...
```

- [ ] **Step 4: 运行截断适配回归**

Run: `python -m unittest tests.test_field_mapping_resolver tests.test_upsert_engine_sqlserver -v`

Expected: all tests `OK`

- [ ] **Step 5: 提交截断策略**

```bash
git add src/core/field_mapping_resolver.py src/config/field_mappings.json tests/test_field_mapping_resolver.py tests/test_upsert_engine_sqlserver.py
git commit -m "feat: add field truncation policy rules"
```

### Task 5: 为 richer checkpoint 状态写红灯测试

**Files:**
- Create: `tests/test_sync_checkpoint_resume.py`
- Modify: `tests/test_form_sync_runner.py`

- [ ] **Step 1: 新建 checkpoint round-trip 与 richer state 测试**

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.retry_manager import CheckpointManager, SyncCheckpoint


class SyncCheckpointResumeTests(unittest.TestCase):
    def test_checkpoint_round_trip_keeps_next_start_row_and_written_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manager = CheckpointManager(checkpoint_dir=tmp_dir)
            checkpoint = SyncCheckpoint(
                form_name="生产订单主表",
                table_name="prd_mo",
                sync_type="full",
                start_row=50000,
                total_fetched=50000,
                total_inserted=49000,
                filter_string="",
                status="pending",
            )
            checkpoint.next_start_row = 50000
            checkpoint.last_written_record_keys = ["FID=1|FBILLNO=MO001"]

            manager.save_checkpoint(checkpoint)
            loaded = manager.load_checkpoint("生产订单主表", "prd_mo", "full")

        self.assertEqual(loaded.next_start_row, 50000)
        self.assertEqual(loaded.last_written_record_keys, ["FID=1|FBILLNO=MO001"])
```

- [ ] **Step 2: 扩展 `tests/test_form_sync_runner.py`，锁住成功写入后保存 richer checkpoint**

```python
    def test_sync_single_form_saves_checkpoint_after_successful_page_write(self) -> None:
        ...
        self.assertEqual(saved_checkpoint.next_start_row, 2)
        self.assertTrue(saved_checkpoint.last_written_record_keys)
```

- [ ] **Step 3: 跑红灯**

Run: `python -m unittest tests.test_sync_checkpoint_resume tests.test_form_sync_runner -v`

Expected:
- `AttributeError` for missing `next_start_row`
- `AttributeError` for missing `last_written_record_keys`
- missing save-after-write assertion

- [ ] **Step 4: 提交红灯 checkpoint 测试**

```bash
git add tests/test_sync_checkpoint_resume.py tests/test_form_sync_runner.py
git commit -m "test: cover p1 checkpoint resume state"
```

### Task 6: 扩展 `SyncCheckpoint` 并在成功写入后持久化

**Files:**
- Modify: `src/core/retry_manager.py`
- Modify: `src/core/form_sync_runner.py`
- Modify: `tests/test_sync_checkpoint_resume.py`
- Modify: `tests/test_form_sync_runner.py`

- [ ] **Step 1: 扩展 checkpoint 数据结构**

```python
@dataclass
class SyncCheckpoint:
    form_name: str
    table_name: str
    sync_type: str
    start_row: int = 0
    total_fetched: int = 0
    total_inserted: int = 0
    last_page: int = 0
    filter_string: str = ""
    timestamp: str = ""
    status: str = "pending"
    next_start_row: int = 0
    last_written_record_keys: list[str] = field(default_factory=list)
    last_error_category: str = ""
```

- [ ] **Step 2: 在 `FormSyncRunner` 每次成功写入后保存 richer checkpoint**

```python
                        total_fetched_ref[0] += len(page_data)
                        failure_details_ref.extend(outcome.failure_details)
                        self.owner._checkpoint_manager.save_checkpoint(
                            SyncCheckpoint(
                                form_name=form_name,
                                table_name=table_name,
                                sync_type=self._sync_type_value(sync_type),
                                start_row=total_fetched_ref[0],
                                next_start_row=total_fetched_ref[0],
                                total_fetched=total_fetched_ref[0],
                                total_inserted=total_inserted_ref[0],
                                filter_string=filter_string or "",
                                status="pending",
                                last_written_record_keys=[detail for detail in outcome.failure_details[0].record_keys] if outcome.failure_details else [],
                                last_error_category="",
                            )
                        )
```

- [ ] **Step 3: 在查询失败保存 checkpoint 时带上最近写入标识**

```python
                                next_start_row=resume_start_row,
                                last_written_record_keys=list(failure_details_ref[-1].record_keys) if failure_details_ref else [],
                                last_error_category="query_error",
```

- [ ] **Step 4: 跑 richer checkpoint 回归**

Run: `python -m unittest tests.test_sync_checkpoint_resume tests.test_form_sync_runner -v`

Expected: all tests `OK`

- [ ] **Step 5: 提交 richer checkpoint 状态**

```bash
git add src/core/retry_manager.py src/core/form_sync_runner.py tests/test_sync_checkpoint_resume.py tests/test_form_sync_runner.py
git commit -m "feat: persist richer sync checkpoint state"
```

### Task 7: 完成 P1 回归与日志口径确认

**Files:**
- Verify: `src/config/field_mappings.json`
- Verify: `src/core/field_mapping_resolver.py`
- Verify: `src/core/retry_manager.py`
- Verify: `src/core/mysql_manager.py`

- [ ] **Step 1: 跑 P1 相关完整回归**

Run: `python -m unittest tests.test_field_mapping_resolver tests.test_prd_mo_cancel_status tests.test_ap_payable_field_mapping tests.test_eng_bomchild_field_mapping tests.test_sync_checkpoint_resume tests.test_form_sync_runner tests.test_upsert_engine_sqlserver -v`

Expected: all tests `OK`

- [ ] **Step 2: 跑 P1 相关 lint 子集**

Run: `python -m ruff check src\config\field_mappings.json src\core\field_mapping_resolver.py src\core\retry_manager.py src\core\mysql_manager.py src\core\form_sync_runner.py tests\test_field_mapping_resolver.py tests\test_sync_checkpoint_resume.py tests\test_prd_mo_cancel_status.py tests\test_ap_payable_field_mapping.py tests\test_eng_bomchild_field_mapping.py tests\test_upsert_engine_sqlserver.py`

Expected: `All checks passed!`

- [ ] **Step 3: 记录预期日志变化**

```text
- 预期 prepare 路径不再把 FCANCELSTATUS / FNOTAXAMOUNTFOR / FCHILDNUMBER / FCHILDNAME 的 source alias 硬编码散落在多处
- 预期字符串超长场景优先按 field_mappings.json 规则处理，诊断日志只作为兜底
- 预期 checkpoint JSON 中新增 next_start_row / last_written_record_keys / last_error_category
- SQL Server 写入相关日志本身不新增结构字段；变化体现在写入失败后 checkpoint 与预处理行为更稳定，重跑不再只能依赖粗粒度 StartRow
```

- [ ] **Step 4: 提交 P1 最终集成**

```bash
git add src/config/field_mappings.json src/core/field_mapping_resolver.py src/core/retry_manager.py src/core/mysql_manager.py src/core/form_sync_runner.py tests/test_field_mapping_resolver.py tests/test_sync_checkpoint_resume.py tests/test_prd_mo_cancel_status.py tests/test_ap_payable_field_mapping.py tests/test_eng_bomchild_field_mapping.py tests/test_upsert_engine_sqlserver.py
git commit -m "feat: deliver p1 mapping and checkpoint semantics"
```

## Self-Review

### Spec coverage

- `3 全局字段映射配置文件` → Task 1, 2, 3
- `2 字段截断自动适配` → Task 4
- `7 断点续传覆盖更多失败场景` → Task 5, 6

### Placeholder scan

- 无 `TODO/TBD`
- 每个任务都有具体文件、代码片段、命令与预期

### Type consistency

- 字段映射统一通过 `FieldMappingResolver`
- checkpoint 扩展统一通过 `SyncCheckpoint.next_start_row` / `last_written_record_keys` / `last_error_category`
- 不引入第二套字段映射配置接口
