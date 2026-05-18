# P0 Evidence And Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地研发优化路线图的 `P0` 波次（`8 写库失败明细日志`、`9 增量同步成功率趋势面板`、`1 FCANCELSTATUS NULL 止血`、`6 熔断机制`），先建立证据链和局部止血能力。

**Architecture:** 在现有同步链路上增加两层轻量基础设施：`sync_failure_telemetry` 负责失败分类、记录标识提取和汇总；`circuit_breaker` 负责按表单的局部熔断。`FormSyncRunner` 继续作为单表执行入口，但要把写库失败明细、成功/失败统计、重试与熔断事件统一上送给 `metrics.py` 和 `sync_runs.details_json`，避免直接改业务 writer 的大范围接口。

**Tech Stack:** Python 3.11, unittest, JSON audit logs, existing `sync_runs`/`sync_logs`, SQL Server/MySQL compatibility layer

---

## File Structure

**Create**

- `src/core/sync_failure_telemetry.py`
- `src/core/circuit_breaker.py`
- `tests/test_sync_failure_telemetry.py`
- `tests/test_circuit_breaker.py`

**Modify**

- `src/core/write_outcome.py`
- `src/core/form_sync_runner.py`
- `src/core/metrics.py`
- `src/core/data_sync.py`
- `src/core/mysql_manager.py`
- `src/config/config_reader.py`
- `src/config/config_accessors.py`
- `tests/test_form_sync_runner.py`
- `tests/test_config_manager.py`

**Why this decomposition**

- `sync_failure_telemetry.py` 把失败分类和写库明细抽成独立单元，避免把这些规则塞回 `form_sync_runner.py`。
- `circuit_breaker.py` 单独承载熔断状态机，避免在 `data_sync.py` 里继续堆条件分支。
- `metrics.py` 只做指标聚合；失败分类规则不放进 `metrics.py`。
- `FormSyncRunner` 仍负责单表执行，但只负责“采集并上送”，不负责定义统计口径。

## Scope Guard

这个 plan **只覆盖 P0**。`3/2/7` 和 `5/4/10` 不进入本计划，原因是：

- `P1` 依赖 `P0` 的失败分类与趋势证据
- `P2` 依赖 `P0/P1` 稳定后的基线数据

后续需要单独写 `P1` 和 `P2` 的计划文件。

### Task 1: 建立失败明细与熔断的红灯测试

**Files:**
- Create: `tests/test_sync_failure_telemetry.py`
- Create: `tests/test_circuit_breaker.py`
- Modify: `tests/test_form_sync_runner.py`
- Modify: `tests/test_config_manager.py`

- [ ] **Step 1: 新建失败分类与标识提取测试**

```python
from __future__ import annotations

import unittest

from src.core.sync_failure_telemetry import (
    WriteFailureDetail,
    build_record_keys,
    classify_failure,
    summarize_failure_details,
)


class SyncFailureTelemetryTests(unittest.TestCase):
    def test_classify_failure_prefers_truncation_keyword(self) -> None:
        detail = classify_failure(
            form_name="生产订单主表",
            table_name="prd_mo",
            error_type="ProgrammingError",
            message="String or binary data would be truncated",
            failed_rows=[{"FID": 101, "FBILLNO": "MO001"}],
        )

        self.assertEqual(detail.category, "string_truncation")
        self.assertEqual(detail.record_keys, ["FID=101|FBILLNO=MO001"])
        self.assertFalse(detail.retryable)

    def test_build_record_keys_prefers_fid_then_billno(self) -> None:
        keys = build_record_keys(
            [
                {"FID": 101, "FBILLNO": "MO001"},
                {"FID": 102, "FBILLNO": "MO002"},
            ]
        )

        self.assertEqual(keys, ["FID=101|FBILLNO=MO001", "FID=102|FBILLNO=MO002"])

    def test_summarize_failure_details_groups_by_category(self) -> None:
        details = [
            WriteFailureDetail(category="sql_error", error_type="IntegrityError", message="dup", failed_count=2),
            WriteFailureDetail(category="sql_error", error_type="IntegrityError", message="dup", failed_count=1),
            WriteFailureDetail(category="session_error", error_type="ValueError", message="session", failed_count=3),
        ]

        summary = summarize_failure_details(details)

        self.assertEqual(summary["sql_error"], 3)
        self.assertEqual(summary["session_error"], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 新建局部熔断红灯测试**

```python
from __future__ import annotations

import unittest

from src.core.circuit_breaker import LocalCircuitBreaker


class LocalCircuitBreakerTests(unittest.TestCase):
    def test_opens_after_threshold_and_resets_on_success(self) -> None:
        breaker = LocalCircuitBreaker(threshold=3, cooldown_seconds=30)

        self.assertTrue(breaker.allow("生产订单主表"))
        breaker.record_failure("生产订单主表", "sql_error")
        breaker.record_failure("生产订单主表", "sql_error")
        breaker.record_failure("生产订单主表", "sql_error")

        self.assertFalse(breaker.allow("生产订单主表"))

        breaker.record_success("生产订单主表")
        self.assertTrue(breaker.allow("生产订单主表"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 扩展 `tests/test_form_sync_runner.py`，锁定 P0 行为**

```python
    def test_sync_single_form_emits_write_failure_audit_and_metrics(self) -> None:
        owner = SimpleNamespace(
            DEDUPLICATION_FORMS=set(),
            INSERT_METHOD_MAP={"销售订单": "insert_sales_orders"},
            table_mapping={"销售订单": "saleorder"},
            _notify_progress=Mock(),
            _checkpoint_manager=SimpleNamespace(load_checkpoint=Mock(return_value=None), clear_checkpoint=Mock()),
        )
        filter_builder = SimpleNamespace(build_filter_string=Mock(return_value=""))
        fake_db = SimpleNamespace(log_sync_operation=Mock(), disconnect=Mock())
        runner = FormSyncRunner(owner, filter_builder, logger_=logging.getLogger("test.form_sync_runner"))

        with (
            patch("src.core.form_sync_runner.create_shared_db_manager", return_value=fake_db),
            patch("src.core.form_sync_runner.emit_audit_log") as mock_audit,
            patch("src.core.form_sync_runner.metrics_collector") as mock_metrics,
            patch("src.core.form_sync_runner.config_manager") as mock_config_manager,
        ):
            mock_config_manager.get_form_queries.return_value = {"销售订单": {"FieldKeys": "FID,FBillNo"}}
            runner.query_kingdee_data = Mock(
                side_effect=lambda *args, **kwargs: kwargs["page_callback"]([{"FID": 1, "FBillNo": "SO001"}]) or []
            )
            runner.insert_database_data = Mock(
                return_value=WriteOutcome(
                    inserted=0,
                    failed=1,
                    failure_details=[
                        {"category": "sql_error", "record_keys": ["FID=1|FBillNo=SO001"], "failed_count": 1}
                    ],
                )
            )

            result = runner.sync_single_form("销售订单", "full")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failure_categories"]["sql_error"], 1)
        mock_metrics.record_write_outcome.assert_called_once()
        self.assertTrue(any(call.kwargs.get("event") == "write_failure_detail" for call in mock_audit.mock_calls))
```

- [ ] **Step 4: 扩展 `tests/test_config_manager.py`，锁定熔断默认配置**

```python
    def test_sync_config_exposes_circuit_breaker_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[KINGDEE]",
                        "login_url = https://example.com/login",
                        "query_url = https://example.com/query",
                        "acct_id = demo",
                        "username = user",
                        "password = plain",
                        "lcid = 2052",
                        "",
                        "[DATABASE]",
                        "type = sqlserver",
                        "",
                        "[MYSQL]",
                        "host = 127.0.0.1",
                        "user = root",
                        "password = plain",
                        "database = kingdee",
                        "charset = utf8mb4",
                        "port = 3306",
                        "",
                        "[SQLSERVER]",
                        "host = 127.0.0.1",
                        "user = sa",
                        "password = plain",
                        "database = kingdee",
                        "port = 1433",
                        "driver = ODBC Driver 17 for SQL Server",
                        "",
                        "[SYNC]",
                        "auto_sync = false",
                        "sync_interval = 60",
                    ]
                ),
                encoding="utf-8",
            )

            manager = ConfigManager(str(config_path))
            sync_config = manager.get_sync_config()

            self.assertTrue(sync_config["circuit_breaker_enabled"])
            self.assertEqual(sync_config["circuit_breaker_threshold"], 3)
            self.assertEqual(sync_config["circuit_breaker_cooldown_secs"], 30)
```

- [ ] **Step 5: 运行红灯测试，确认按预期失败**

Run: `python -m unittest tests.test_sync_failure_telemetry tests.test_circuit_breaker tests.test_form_sync_runner tests.test_config_manager -v`

Expected:
- `ModuleNotFoundError` for `src.core.sync_failure_telemetry`
- `ModuleNotFoundError` for `src.core.circuit_breaker`
- `AttributeError` / `AssertionError` around missing `record_write_outcome`
- `KeyError` for new sync config keys

- [ ] **Step 6: 提交红灯测试**

```bash
git add tests/test_sync_failure_telemetry.py tests/test_circuit_breaker.py tests/test_form_sync_runner.py tests/test_config_manager.py
git commit -m "test: cover p0 sync failure telemetry"
```

### Task 2: 实现失败明细模型与趋势指标聚合

**Files:**
- Create: `src/core/sync_failure_telemetry.py`
- Modify: `src/core/write_outcome.py`
- Modify: `src/core/metrics.py`
- Modify: `src/core/form_sync_runner.py`
- Test: `tests/test_sync_failure_telemetry.py`
- Test: `tests/test_form_sync_runner.py`

- [ ] **Step 1: 新建失败明细模型**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(slots=True)
class WriteFailureDetail:
    category: str
    error_type: str
    message: str
    failed_count: int = 0
    retryable: bool = False
    record_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "error_type": self.error_type,
            "message": self.message,
            "failed_count": self.failed_count,
            "retryable": self.retryable,
            "record_keys": list(self.record_keys),
        }


def build_record_keys(rows: Iterable[dict[str, Any]], limit: int = 5) -> list[str]:
    keys: list[str] = []
    for row in rows:
        fid = row.get("FID") or row.get("FId")
        bill_no = row.get("FBILLNO") or row.get("FBillNo")
        entry_id = row.get("FENTRYID") or row.get("FEntryId")
        parts = []
        if fid is not None:
            parts.append(f"FID={fid}")
        if bill_no:
            parts.append(f"FBILLNO={bill_no}")
        if entry_id is not None:
            parts.append(f"FENTRYID={entry_id}")
        if parts:
            keys.append("|".join(parts))
        if len(keys) >= limit:
            break
    return keys


def classify_failure(
    *,
    form_name: str,
    table_name: str,
    error_type: str,
    message: str,
    failed_rows: list[dict[str, Any]] | None = None,
) -> WriteFailureDetail:
    lowered = str(message).lower()
    if "truncat" in lowered:
        category = "string_truncation"
        retryable = False
    elif "会话" in message or "重新登录" in message:
        category = "session_error"
        retryable = True
    elif "timeout" in lowered or "connection" in lowered:
        category = "network_error"
        retryable = True
    elif "integrity" in lowered or "duplicate" in lowered or "constraint" in lowered:
        category = "sql_error"
        retryable = False
    else:
        category = "unexpected_error"
        retryable = False

    rows = failed_rows or []
    return WriteFailureDetail(
        category=category,
        error_type=error_type,
        message=message,
        failed_count=max(1, len(rows)),
        retryable=retryable,
        record_keys=build_record_keys(rows),
    )


def summarize_failure_details(details: Iterable[WriteFailureDetail]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for detail in details:
        summary[detail.category] = summary.get(detail.category, 0) + int(detail.failed_count or 0)
    return summary
```

- [ ] **Step 2: 扩展 `WriteOutcome` 以承载失败明细**

```python
from dataclasses import dataclass, field

from src.core.sync_failure_telemetry import WriteFailureDetail


@dataclass(slots=True)
class WriteOutcome:
    inserted: int = 0
    invalid: int = 0
    deduped: int = 0
    failed: int = 0
    failure_details: list[WriteFailureDetail] = field(default_factory=list)

    @classmethod
    def from_insert_count(cls, inserted: int) -> "WriteOutcome":
        return cls(inserted=max(0, int(inserted or 0)))
```

- [ ] **Step 3: 在 `metrics.py` 增加写库结果聚合与趋势快照**

```python
@dataclass
class SyncMetrics:
    form_name: str
    start_time: float = 0.0
    end_time: float = 0.0
    records_fetched: int = 0
    records_inserted: int = 0
    records_failed: int = 0
    records_invalid: int = 0
    records_deduped: int = 0
    failure_categories: dict[str, int] = field(default_factory=dict)

    def to_trend_dict(self) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "records_invalid": self.records_invalid,
            "records_deduped": self.records_deduped,
            "failure_categories": dict(self.failure_categories),
        }


class MetricsCollector:
    def record_write_outcome(self, form_name: str, outcome: WriteOutcome, duration: float) -> None:
        with self._lock:
            metrics = self._current_metrics.get(form_name)
            if not metrics:
                return
            metrics.records_inserted += outcome.inserted
            metrics.records_failed += outcome.failed
            metrics.records_invalid += outcome.invalid
            metrics.records_deduped += outcome.deduped
            metrics.db_insert_time += duration
            for detail in outcome.failure_details:
                metrics.failure_categories[detail.category] = (
                    metrics.failure_categories.get(detail.category, 0) + detail.failed_count
                )
```

- [ ] **Step 4: 在 `form_sync_runner.py` 接入失败明细和趋势事件**

```python
from src.core.metrics import metrics_collector
from src.core.sync_failure_telemetry import classify_failure, summarize_failure_details


def sync_single_form(self, form_name: str, sync_type) -> Dict[str, Any]:
    metrics_collector.start_sync(form_name)
    ...
    try:
        ...
        if use_bulk_buffer and all_rows_buffer:
            write_start = time.perf_counter()
            outcome = self.insert_database_data(form_name, all_rows_buffer, db_manager=local_db)
            metrics_collector.record_write_outcome(form_name, outcome, time.perf_counter() - write_start)
        ...
        summary = self._build_write_summary(form_name, fetched=record_count, outcome=outcome)
        failure_categories = summarize_failure_details(outcome.failure_details)
        for detail in outcome.failure_details:
            emit_audit_log(
                self.logger,
                "sync_form",
                "write_failure_detail",
                level="warning",
                form_name=form_name,
                table_name=table_name,
                category=detail.category,
                error_type=detail.error_type,
                failed_count=detail.failed_count,
                record_keys=detail.record_keys,
            )
        result = {
            ...
            "failure_categories": failure_categories,
            "failure_details": [detail.to_dict() for detail in outcome.failure_details],
        }
        metrics_collector.end_sync(form_name, success=result_status == SUCCESS_STATUS)
        return result
    except Exception as exc:
        metrics_collector.record_error(form_name)
        metrics_collector.end_sync(form_name, success=False)
        ...
```

- [ ] **Step 5: 在 writer 结果缺少明细时，至少生成批级失败详情**

```python
def insert_database_data(self, form_name: str, data: List[Dict], db_manager=None) -> WriteOutcome:
    manager = db_manager or mysql_manager
    method_name = self.owner.INSERT_METHOD_MAP.get(form_name)
    if method_name:
        try:
            return manager.execute_writer_with_outcome(method_name, data)
        except Exception as exc:
            detail = classify_failure(
                form_name=form_name,
                table_name=self.owner.table_mapping.get(form_name, ""),
                error_type=type(exc).__name__,
                message=str(exc),
                failed_rows=data[:5],
            )
            return WriteOutcome(failed=len(data), failure_details=[detail])
```

- [ ] **Step 6: 运行测试转绿**

Run: `python -m unittest tests.test_sync_failure_telemetry tests.test_form_sync_runner -v`

Expected: all tests `OK`

- [ ] **Step 7: 提交失败明细与趋势聚合基础设施**

```bash
git add src/core/sync_failure_telemetry.py src/core/write_outcome.py src/core/metrics.py src/core/form_sync_runner.py tests/test_sync_failure_telemetry.py tests/test_form_sync_runner.py
git commit -m "feat: add sync failure telemetry primitives"
```

### Task 3: 修复 `FCANCELSTATUS` 空值止血

**Files:**
- Modify: `src/core/mysql_manager.py`
- Modify: `tests/test_form_sync_runner.py`
- Create: `tests/test_prd_mo_cancel_status.py`

- [ ] **Step 1: 为生产订单空取消状态写红灯测试**

```python
from __future__ import annotations

import unittest

from src.core.mysql_manager import MySQLManager


class PrdMoCancelStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MySQLManager.__new__(MySQLManager)
        self.manager._to_int_or_none = lambda value: int(value) if value not in (None, "") else None
        self.manager._safe_str = lambda value: None if value in (None, "") else str(value).strip()
        self.manager._parse_datetime = lambda value: value
        self.manager._convert_production_status = lambda value: value or ""

    def test_prepare_production_order_defaults_null_cancel_status_to_empty_string(self) -> None:
        row = self.manager._prepare_production_order_data(
            {
                "FID": 101,
                "FBILLNO": "MO001",
                "FBILLTYPE.FNAME": "标准生产订单",
                "FDATE": "2026-05-18 08:00:00",
                "FPRDORGID": 100,
                "FWORKSHOPID": 200,
                "FDOCUMENTSTATUS": "A",
                "FCREATEDATE": "2026-05-18 08:00:00",
                "FMODIFYDATE": "2026-05-18 09:00:00",
                "FCANCELSTATUS": None,
            }
        )

        self.assertEqual(row[-1], "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 在生产订单准备函数里显式归一化空值**

```python
def _prepare_production_order_data(self, item) -> Optional[Tuple]:
    ...
    fcancel = self._safe_str(item.get("FCANCELSTATUS") or item.get("FCancelStatus"))
    if fcancel is None:
        fcancel = ""
    return (
        fid,
        fbillno,
        fbilltype,
        fdate,
        fprdorgid,
        fworkshopid,
        fdocstatus,
        fcreated,
        fmodifydate,
        fcancel,
    )
```

- [ ] **Step 3: 运行定向测试**

Run: `python -m unittest tests.test_prd_mo_cancel_status tests.test_sqlserver_business_layout -v`

Expected: all tests `OK`

- [ ] **Step 4: 提交 `FCANCELSTATUS` 止血修复**

```bash
git add src/core/mysql_manager.py tests/test_prd_mo_cancel_status.py tests/test_sqlserver_business_layout.py
git commit -m "fix: normalize prd mo cancel status"
```

### Task 4: 加入局部熔断与配置默认值

**Files:**
- Create: `src/core/circuit_breaker.py`
- Modify: `src/config/config_reader.py`
- Modify: `src/config/config_accessors.py`
- Modify: `src/core/data_sync.py`
- Modify: `tests/test_circuit_breaker.py`
- Modify: `tests/test_config_manager.py`

- [ ] **Step 1: 在配置默认值里加入熔断开关**

```python
    "SYNC": {
        "auto_sync": "False",
        "sync_interval": "60",
        "last_sync_time": "",
        "sync_type": "incremental",
        "default_forms": "",
        "fetch_concurrency": "4",
        "table_concurrency": "4",
        "time_window_days": "30",
        "full_start_date": "2000-01-01",
        "run_heartbeat_interval_secs": "15",
        "run_heartbeat_timeout_secs": "120",
        "circuit_breaker_enabled": "true",
        "circuit_breaker_threshold": "3",
        "circuit_breaker_cooldown_secs": "30",
    },
```

- [ ] **Step 2: 在 `config_accessors.py` 暴露熔断配置**

```python
    sync_config["circuit_breaker_enabled"] = _as_bool(
        sync_config.get("circuit_breaker_enabled", "true"),
        True,
    )
    sync_config["circuit_breaker_threshold"] = max(
        1,
        _as_int(sync_config.get("circuit_breaker_threshold", "3"), 3),
    )
    sync_config["circuit_breaker_cooldown_secs"] = max(
        5,
        _as_int(sync_config.get("circuit_breaker_cooldown_secs", "30"), 30),
    )
```

- [ ] **Step 3: 实现最小局部熔断状态机**

```python
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float = 0.0


class LocalCircuitBreaker:
    def __init__(self, threshold: int, cooldown_seconds: int) -> None:
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[str, CircuitState] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now_value = now or time.time()
        state = self._states.get(key)
        if not state:
            return True
        return state.opened_until <= now_value

    def record_failure(self, key: str, category: str, now: float | None = None) -> None:
        now_value = now or time.time()
        state = self._states.setdefault(key, CircuitState())
        state.failures += 1
        if state.failures >= self.threshold:
            state.opened_until = now_value + self.cooldown_seconds

    def record_success(self, key: str) -> None:
        self._states[key] = CircuitState()
```

- [ ] **Step 4: 在 `data_sync.py` 调度入口接入熔断**

```python
from src.core.circuit_breaker import LocalCircuitBreaker


class DataSyncManager:
    def __init__(self):
        ...
        sync_config = config_manager.get_sync_config()
        self._circuit_breaker = LocalCircuitBreaker(
            threshold=sync_config.get("circuit_breaker_threshold", 3),
            cooldown_seconds=sync_config.get("circuit_breaker_cooldown_secs", 30),
        )
        self._circuit_breaker_enabled = sync_config.get("circuit_breaker_enabled", True)

    def _sync_single_form(self, form_name: str, sync_type: SyncType) -> dict[str, Any]:
        if self._circuit_breaker_enabled and not self._circuit_breaker.allow(form_name):
            return {
                "status": SyncStatus.FAILED.value,
                "message": f"{form_name} 已进入熔断冷却期，暂缓 30 秒后再试",
                "record_count": 0,
                "error_type": "circuit_open",
            }

        result = self.form_sync_runner.sync_single_form(form_name, sync_type)
        if result.get("status") == SyncStatus.SUCCESS.value:
            self._circuit_breaker.record_success(form_name)
        else:
            categories = result.get("failure_categories") or {}
            primary_category = next(iter(categories.keys()), result.get("error_type", "unknown"))
            self._circuit_breaker.record_failure(form_name, primary_category)
        return result
```

- [ ] **Step 5: 运行熔断与配置测试**

Run: `python -m unittest tests.test_circuit_breaker tests.test_config_manager tests.test_data_sync_shutdown -v`

Expected: all tests `OK`

- [ ] **Step 6: 提交熔断与配置默认值**

```bash
git add src/core/circuit_breaker.py src/core/data_sync.py src/config/config_reader.py src/config/config_accessors.py tests/test_circuit_breaker.py tests/test_config_manager.py
git commit -m "feat: add local sync circuit breaker"
```

### Task 5: 将趋势指标写入任务级详情并完成 P0 验证

**Files:**
- Modify: `src/core/data_sync.py`
- Modify: `src/core/metrics.py`
- Modify: `tests/test_form_sync_runner.py`
- Verify: `src/core/sync_run_repository.py`

- [ ] **Step 1: 在 `DataSyncManager._finalize_run` 写入表单趋势快照**

```python
from src.core.metrics import metrics_collector


    def _finalize_run(...):
        ...
        metrics_snapshot = {
            form_name: metrics_collector.get_form_stats(form_name)
            for form_name in requested_forms
        }
        details_payload = {
            "results": results,
            "metrics": metrics_snapshot,
            "failed_forms": failed_tables,
        }
        mysql_manager.finish_sync_run(
            run_id=run_id,
            sync_type=sync_type.value,
            forms=requested_forms,
            total_records=total_records,
            success_count=success_count,
            failure_count=failure_count,
            status=run_status.value,
            message=message,
            start_time=start_time,
            end_time=final_dt,
            failed_forms=failed_tables,
            details=details_payload,
        )
```

- [ ] **Step 2: 扩展表单结果测试，锁定 metrics 快照结构**

```python
    def test_sync_single_form_returns_failure_categories_for_partial_write(self) -> None:
        ...
        self.assertEqual(result["failure_categories"], {"sql_error": 1})
        self.assertIn("failure_details", result)
```

- [ ] **Step 3: 运行 P0 相关完整回归**

Run: `python -m unittest tests.test_sync_failure_telemetry tests.test_circuit_breaker tests.test_form_sync_runner tests.test_prd_mo_cancel_status tests.test_kingdee_api tests.test_config_manager tests.test_data_sync_shutdown tests.test_sqlserver_business_layout -v`

Expected: all tests `OK`

- [ ] **Step 4: 运行门禁子集**

Run: `python -m ruff check src\core\sync_failure_telemetry.py src\core\circuit_breaker.py src\core\form_sync_runner.py src\core\data_sync.py src\core\metrics.py src\core\mysql_manager.py tests\test_sync_failure_telemetry.py tests\test_circuit_breaker.py tests\test_form_sync_runner.py tests\test_prd_mo_cancel_status.py tests\test_config_manager.py`

Expected: `All checks passed!`

- [ ] **Step 5: 记录预期日志变化**

```text
- 预期新增结构化审计事件 `write_failure_detail`
- 预期单表结果中新增 `failure_categories` 和 `failure_details`
- 预期 `sync_runs.details_json` 中新增 `metrics` 快照
- SQL Server 写入链路本身不变；变化是失败原因不再只以一句 message 聚合，而能区分 `string_truncation`、`session_error`、`network_error`、`sql_error`
```

- [ ] **Step 6: 提交 P0 最终集成**

```bash
git add src/core/data_sync.py src/core/metrics.py tests/test_form_sync_runner.py
git commit -m "feat: capture p0 sync failure evidence"
```

## Self-Review

### Spec coverage

- `8 写库失败明细日志` → Task 1, 2, 5
- `9 增量同步成功率趋势面板` → Task 2, 5
- `1 FCANCELSTATUS NULL 问题` → Task 3
- `6 熔断机制` → Task 1, 4

`P1/P2` 未覆盖，属于有意排除，不是遗漏。

### Placeholder scan

- 无 `TODO/TBD`
- 每个改动步骤都给了目标代码或测试代码
- 每个验证步骤都有确切命令和预期结果

### Type consistency

- 失败明细统一使用 `WriteFailureDetail`
- 运行结果统一暴露 `failure_categories` / `failure_details`
- 熔断状态机统一通过 `LocalCircuitBreaker` 暴露 `allow / record_failure / record_success`
