# Kingdee Sync Error Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复金蝶同步故障链，确保会话失效响应不会混入业务数据流、`prd_instock` 坏记录不会拖垮整批写入、应用退出后不会继续排任务或向已销毁的 GUI 信号发消息。

**Architecture:** 在现有同步架构内做三层补强。查询入口层在 `src/core/kingdee_api.py` 收紧响应识别并处理会话错误重登；写库层通过新的 `WriteOutcome` 结果对象把 `invalid/deduped/inserted` 从 `prd_instock` 和 SQL Server upsert 路径上传给 `FormSyncRunner`；生命周期层在 `DataSyncManager`、`AutoSyncScheduler`、GUI 日志桥和退出入口之间增加 shutdown 守卫，阻止退出阶段继续扩散工作。

**Tech Stack:** Python 3.11、requests、schedule、PySide6、unittest、SQL Server/MySQL upsert engine

---

## Preflight

在开始 Task 1 之前，先切到单独 worktree，避免当前工作区里的 `.DS_Store` 改动污染实现分支。

```bash
git worktree add ../Kingdee-error-chain -b codex/kingdee-error-chain
cd ../Kingdee-error-chain
git status --short
python3 -m pip install -r requirements.txt
```

预期输出：

- `git worktree add` 成功创建 `../Kingdee-error-chain`
- `git status --short` 输出为空
- `python3 -m pip install -r requirements.txt` 输出 `Requirement already satisfied` 或成功安装依赖

## File Structure

- Create: `src/core/write_outcome.py`
  - 统一定义写库结果对象，承载 `inserted`、`invalid`、`deduped`、`failed`
- Create: `tests/test_kingdee_api.py`
  - 覆盖列表包裹错误响应、会话错误重登重试、错误响应不进入业务数据流
- Create: `tests/test_prd_instock_write_validation.py`
  - 覆盖 `_prepare_prd_instock_data()` 严格校验、`UpsertEngineSqlServer` 必填字段过滤、`execute_writer_with_outcome()` 结果归一化
- Create: `tests/test_form_sync_runner.py`
  - 覆盖 `FormSyncRunner` 对 `WriteOutcome` 的统计归并与日志口径
- Create: `tests/test_data_sync_shutdown.py`
  - 覆盖 `DataSyncManager` shutdown 守卫和 `AutoSyncScheduler` 停止后不再启动新同步
- Create: `tests/test_gui_logging_utils.py`
  - 覆盖 `GuiLogHandler` 对已销毁 Qt 信号源的静默保护
- Modify: `src/core/kingdee_api.py`
  - 增加查询响应归一化、错误提取、会话错误识别和页级重登重试
- Modify: `src/core/mysql_manager.py`
  - 严格校验 `prd_instock` 关键字段；新增 `execute_writer_with_outcome()` 收集 `WriteOutcome`，保留现有 `execute_writer()` 兼容行为
- Modify: `src/core/upsert_engine_sqlserver.py`
  - 为 `prd_instock` 增加 `FBILLNO` 必填过滤；把 `invalid/deduped/inserted` 通过 `WriteOutcome` 返回
- Modify: `src/core/form_sync_runner.py`
  - 让单表同步流程消费 `WriteOutcome`，输出 `fetched/invalid/deduped/inserted/failed`
- Modify: `src/core/data_sync.py`
  - 新增 shutdown 状态，退出阶段不再创建新的 `ThreadPoolExecutor` 任务
- Modify: `src/core/scheduler.py`
  - 当 scheduler 停止或 sync manager 已进入 shutdown 状态时，不再触发 `_execute_sync()`
- Modify: `src/utils/kingdee_sync_tool.py`
  - 调整 `cleanup_and_exit()` 顺序，先请求 shutdown，再停 scheduler，再释放资源
- Modify: `src/gui/logging_utils.py`
  - 吞掉 `Signal source has been deleted` 之类的 `RuntimeError`

## Task 1: Harden Kingdee Query Response Classification

**Files:**
- Modify: `src/core/kingdee_api.py`
- Test: `tests/test_kingdee_api.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.core.kingdee_api import KingdeeAPIClient


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class KingdeeAPIClientQueryTests(unittest.TestCase):
    def _make_client(self) -> KingdeeAPIClient:
        with patch("src.core.kingdee_api.config_manager") as mock_config_manager:
            mock_config_manager.get_kingdee_config.return_value = {
                "ssl_verify": "false",
                "login_url": "https://example.com/login",
                "query_url": "https://example.com/query",
                "rate_limit_qps": 0,
                "request_retries": 1,
                "retry_base_delay": 0.01,
                "retry_max_delay": 0.01,
                "request_connect_timeout": 5,
                "request_read_timeout": 5,
                "max_request_read_timeout": 5,
                "page_size": 20000,
                "max_pages": 2,
            }
            client = KingdeeAPIClient()
        client.is_authenticated = True
        return client

    def test_query_data_rejects_list_wrapped_session_error_payload(self) -> None:
        client = self._make_client()
        client.session.post = Mock(
            return_value=FakeResponse(
                [
                    {
                        "Result": {
                            "ResponseStatus": {
                                "IsSuccess": False,
                                "Errors": [{"Message": "会话信息已丢失，请重新登录"}],
                            }
                        }
                    }
                ]
            )
        )

        rows = client.query_data(
            "销售订单",
            {
                "FormId": "SAL_SaleOrder",
                "FieldKeys": "FID,FBillNo",
                "StartRow": 0,
                "Limit": 0,
            },
        )

        self.assertIsNone(rows)

    def test_query_data_retries_same_page_once_after_session_error(self) -> None:
        client = self._make_client()
        client.logout = Mock()
        client.login = Mock(return_value=True)
        client.session.post = Mock(
            side_effect=[
                FakeResponse(
                    {
                        "Result": {
                            "ResponseStatus": {
                                "IsSuccess": False,
                                "Errors": [{"Message": "会话信息已丢失，请重新登录"}],
                            }
                        }
                    }
                ),
                FakeResponse(
                    {
                        "Result": {
                            "ResponseStatus": {"IsSuccess": True},
                            "Result": [[1, "SO001"]],
                        }
                    }
                ),
            ]
        )

        rows = client.query_data(
            "销售订单",
            {
                "FormId": "SAL_SaleOrder",
                "FieldKeys": "FID,FBillNo",
                "StartRow": 0,
                "Limit": 0,
            },
        )

        self.assertEqual(rows, [{"FID": 1, "FBillNo": "SO001"}])
        client.logout.assert_called_once_with(force=True)
        client.login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_kingdee_api -v
```

Expected:

- `test_query_data_rejects_list_wrapped_session_error_payload` 失败，因为当前实现会把列表包裹的错误对象当成数据处理
- `test_query_data_retries_same_page_once_after_session_error` 失败，因为当前实现不会在页级会话错误后执行强制重登重试

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/kingdee_api.py
class KingdeeAPIClient:
    SESSION_ERROR_KEYWORDS = ("会话信息已丢失", "请重新登录")

    def _extract_response_status(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            result = payload.get("Result")
            if isinstance(result, dict):
                return result.get("ResponseStatus", {}) or {}
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            wrapped = payload[0].get("Result")
            if isinstance(wrapped, dict):
                return wrapped.get("ResponseStatus", {}) or {}
        return {}

    def _extract_response_errors(self, payload: Any) -> list[str]:
        status = self._extract_response_status(payload)
        errors = status.get("Errors", []) or []
        messages: list[str] = []
        for item in errors:
            if isinstance(item, dict):
                message = item.get("Message") or item.get("FieldName")
                if message:
                    messages.append(str(message))
            elif item:
                messages.append(str(item))
        return messages

    def _is_session_error(self, messages: list[str]) -> bool:
        joined = " ".join(messages)
        return any(keyword in joined for keyword in self.SESSION_ERROR_KEYWORDS)

    def _extract_business_rows(self, payload: Any) -> tuple[list[Any], list[str]]:
        errors = self._extract_response_errors(payload)
        if errors:
            return [], errors

        if isinstance(payload, dict):
            result = payload.get("Result", {})
            if isinstance(result, dict):
                if "Rows" in result:
                    return result.get("Rows", []) or [], []
                if "Result" in result:
                    return result.get("Result", []) or [], []
            return [], ["未知的字典响应结构"]

        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict) and "Result" in payload[0]:
                wrapped = payload[0]["Result"]
                if isinstance(wrapped, dict):
                    return wrapped.get("Result", []) or [], []
                return [], ["未知的列表包裹响应结构"]
            return payload, []

        return [], [f"未知的返回结构类型: {type(payload).__name__}"]
```

```python
# src/core/kingdee_api.py inside query_data()
            session_retry_used = False

            while True:
                page_index += 1
                if page_index > max_pages:
                    logger.warning(
                        "[%s] 分页次数达到安全上限(%s)，提前结束。当前 StartRow=%s",
                        form_id,
                        max_pages,
                        start_row,
                    )
                    break

                if use_paging:
                    query_params["StartRow"] = start_row
                    query_params["Limit"] = page_size
                    query_params.pop("TopRowCount", None)
                    logger.info("[%s] Page %s Request: StartRow=%s, Limit=%s", form_id, page_index, start_row, page_size)

                response, _ = retry_manager.execute_with_retry(
                    _do_request,
                    f"第{page_index}页查询",
                    form_id,
                    on_retry=_on_retry,
                )
                if response.status_code != 200:
                    logger.error("查询请求失败，状态码: %s", response.status_code)
                    return None

                result = response.json()
                page_rows, errors = self._extract_business_rows(result)
                if errors:
                    logger.error("查询失败: %s", errors)
                    if self._is_session_error(errors) and not session_retry_used:
                        logger.warning("[%s] 当前页检测到会话异常，尝试重登后重试...", form_id)
                        self.logout(force=True)
                        if self.login():
                            session_retry_used = True
                            page_index -= 1
                            continue
                    return None

                session_retry_used = False

                if page_rows and isinstance(page_rows[0], list):
                    field_keys_str = query_params.get("FieldKeys", "")
                    if field_keys_str:
                        keys = [k.strip() for k in field_keys_str.split(",") if k.strip()]
                        page_rows = [dict(zip(keys, row_vals)) for row_vals in page_rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_kingdee_api -v
```

Expected:

- 2 个测试均为 `ok`
- 日志允许输出 `查询失败` 和 `当前页检测到会话异常，尝试重登后重试...`

- [ ] **Step 5: Commit**

```bash
git add src/core/kingdee_api.py tests/test_kingdee_api.py
git commit -m "fix: reject kingdee session error payloads"
```

## Task 2: Add WriteOutcome and PRD_INSTOCK Validation

**Files:**
- Create: `src/core/write_outcome.py`
- Modify: `src/core/mysql_manager.py`
- Modify: `src/core/upsert_engine_sqlserver.py`
- Test: `tests/test_prd_instock_write_validation.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.core.mysql_manager import MySQLManager
from src.core.upsert_engine_sqlserver import UpsertEngineSqlServer
from src.core.write_outcome import WriteOutcome


class PrdInstockPrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MySQLManager.__new__(MySQLManager)
        self.manager._last_write_outcome = WriteOutcome()

    def test_prepare_prd_instock_data_skips_blank_billno(self) -> None:
        row = {
            "FID": 1,
            "FEntity_FENTRYID": 2,
            "FBILLNO": "   ",
            "FDATE": "2026-04-20 08:00:00",
        }

        prepared = MySQLManager._prepare_prd_instock_data(self.manager, row)

        self.assertIsNone(prepared)

    def test_execute_writer_with_outcome_wraps_legacy_insert_count(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.writer_registry = SimpleNamespace(execute=lambda *_args, **_kwargs: 3)
        manager._last_write_outcome = WriteOutcome()

        outcome = MySQLManager.execute_writer_with_outcome(manager, "insert_prd_instock", [])

        self.assertEqual(outcome, WriteOutcome(inserted=3))


class SqlServerRequiredFieldFilterTests(unittest.TestCase):
    def test_filter_required_rows_counts_blank_billno_as_invalid(self) -> None:
        engine = UpsertEngineSqlServer(SimpleNamespace())

        filtered, outcome = engine._filter_required_rows(
            "prd_instock",
            ["FID", "FENTRYID", "FBILLNO"],
            [
                [1, 10, "RK20260420"],
                [2, 20, "   "],
                [3, None, "RK20260421"],
            ],
        )

        self.assertEqual(filtered, [[1, 10, "RK20260420"]])
        self.assertEqual(outcome.invalid, 2)
        self.assertEqual(outcome.inserted, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_prd_instock_write_validation -v
```

Expected:

- 导入 `WriteOutcome` 失败，因为文件尚不存在
- `_prepare_prd_instock_data()` 不会把空白 `FBILLNO` 视为无效
- `UpsertEngineSqlServer` 还没有 `_filter_required_rows()`

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/write_outcome.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WriteOutcome:
    inserted: int = 0
    invalid: int = 0
    deduped: int = 0
    failed: int = 0

    @classmethod
    def from_insert_count(cls, inserted: int) -> "WriteOutcome":
        return cls(inserted=max(0, int(inserted or 0)))
```

```python
# src/core/mysql_manager.py
from src.core.write_outcome import WriteOutcome

def execute_writer_with_outcome(self, method_name: str, data: List[Dict]) -> WriteOutcome:
    self._last_write_outcome = WriteOutcome()
    inserted = self.writer_registry.execute(self, method_name, data)
    if self._last_write_outcome.inserted == 0:
        self._last_write_outcome.inserted = max(0, int(inserted or 0))
    return self._last_write_outcome

def execute_writer(self, method_name: str, data: List[Dict]) -> int:
    return self.execute_writer_with_outcome(method_name, data).inserted
```

```python
# src/core/mysql_manager.py inside _prepare_prd_instock_data()
                raw_fid = item.get("FID") or item.get("FId") or item.get("Id")
                fid = self._to_int_or_none(raw_fid)
                raw_fentryid = item.get("FEntity_FENTRYID") or item.get("FENTRYID")
                fentryid = self._to_int_or_none(raw_fentryid)
                billno = self._extract_scalar(item.get("FBILLNO") or item.get("FBillNo"))
                billno = str(billno).strip() if billno is not None else ""

                if fid is None or fentryid is None:
                    self._last_write_outcome.invalid += 1
                    logger.warning(
                        "生产入库单主键为空，已跳过: FID=%s(%s) FENTRYID=%s(%s) FBILLNO=%s",
                        raw_fid,
                        type(raw_fid).__name__,
                        raw_fentryid,
                        type(raw_fentryid).__name__,
                        billno,
                    )
                    return None

                if not billno:
                    self._last_write_outcome.invalid += 1
                    logger.warning("生产入库单单号为空，已跳过: FID=%s FENTRYID=%s", fid, fentryid)
                    return None

            elif isinstance(item, list) and len(item) >= 1:
                get_item = lambda i: (item[i] if i < len(item) else None)
                raw_fid = get_item(0)
                raw_fentryid = get_item(1)
                fid = self._to_int_or_none(raw_fid)
                fentryid = self._to_int_or_none(raw_fentryid)
                billno = str(self._extract_scalar(get_item(2)) or "").strip()
                if fid is None or fentryid is None:
                    self._last_write_outcome.invalid += 1
                    logger.warning("生产入库单主键为空，已跳过: FID=%s FENTRYID=%s", raw_fid, raw_fentryid)
                    return None
                if not billno:
                    self._last_write_outcome.invalid += 1
                    logger.warning("生产入库单单号为空，已跳过: FID=%s FENTRYID=%s", fid, fentryid)
                    return None
```

```python
# src/core/upsert_engine_sqlserver.py
from src.core.write_outcome import WriteOutcome

def _filter_required_rows(
    self,
    table: str,
    columns: List[str],
    values: List[List[Any]],
) -> tuple[List[List[Any]], WriteOutcome]:
    required_map = {
        "sal_deliverynotice": ["FID", "FENTRYID"],
        "prd_instock": ["FID", "FENTRYID", "FBILLNO"],
        "ap_payable": ["FID", "FENTRYID"],
    }
    table_name = str(table).split(".")[-1].replace("[", "").replace("]", "").strip().lower()
    required_cols = required_map.get(table_name, [])
    if not required_cols:
        return values, WriteOutcome()

    required_indices = []
    for required_col in required_cols:
        for index, column in enumerate(columns):
            if str(column).strip().upper() == required_col:
                required_indices.append(index)
                break

    filtered: List[List[Any]] = []
    invalid_required = 0
    for row in values:
        try:
            if any((row[i] is None) or (str(row[i]).strip() == "") for i in required_indices):
                invalid_required += 1
                continue
        except Exception:
            invalid_required += 1
            continue
        filtered.append(row)

    if invalid_required > 0:
        self.logger.warning("[%s] 必填字段为空已跳过: %s 条", table, invalid_required)
    return filtered, WriteOutcome(invalid=invalid_required)

def _finalize_outcome(
    self,
    inserted: int,
    required_outcome: WriteOutcome,
    deduped_count: int,
) -> int:
    self.manager._last_write_outcome = WriteOutcome(
        inserted=inserted,
        invalid=required_outcome.invalid,
        deduped=deduped_count,
    )
    return inserted
```

```python
# src/core/upsert_engine_sqlserver.py inside execute(), right after `base_name = ...`
            values, required_outcome = self._filter_required_rows(base_name, columns, values)
            deduped_count = 0
            pk_raw = manager._get_primary_key(table) or columns[0]
            pk_cols = [c.strip() for c in pk_raw.split(",")] if isinstance(pk_raw, str) and "," in pk_raw else [pk_raw]
            pk_indices = []
            for pkc in pk_cols:
                for i, column in enumerate(columns):
                    if str(column).strip().upper() == str(pkc).strip().upper():
                        pk_indices.append(i)
                        break
            if pk_indices and source_dedup_enabled:
                dedup_map = {}
                duplicate_counter = 0
                for row in values:
                    key_tuple = tuple(manager._hashable_key(row[i]) for i in pk_indices)
                    if any((kv is None) or (str(kv).strip() == "") for kv in key_tuple):
                        required_outcome.invalid += 1
                        continue
                    if key_tuple in dedup_map:
                        duplicate_counter += 1
                    dedup_map[key_tuple] = row
                values = list(dedup_map.values())
                deduped_count = duplicate_counter
```

```python
# src/core/upsert_engine_sqlserver.py before every `return total_inserted`
                        return self._finalize_outcome(
                            total_inserted,
                            required_outcome,
                            deduped_count,
                        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_prd_instock_write_validation -v
```

Expected:

- 3 个测试均为 `ok`
- 日志允许输出 `生产入库单单号为空，已跳过` 和 `[prd_instock] 必填字段为空已跳过`

- [ ] **Step 5: Commit**

```bash
git add src/core/write_outcome.py src/core/mysql_manager.py src/core/upsert_engine_sqlserver.py tests/test_prd_instock_write_validation.py
git commit -m "fix: validate prd instock required fields"
```

## Task 3: Surface Invalid and Failed Counts in FormSyncRunner

**Files:**
- Modify: `src/core/form_sync_runner.py`
- Test: `tests/test_form_sync_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace

from src.core.form_sync_runner import FormSyncRunner
from src.core.write_outcome import WriteOutcome


class FormSyncRunnerSummaryTests(unittest.TestCase):
    def test_build_write_summary_separates_invalid_deduped_and_failed(self) -> None:
        owner = SimpleNamespace(DEDUPLICATION_FORMS={"生产入库单"})
        runner = FormSyncRunner(owner, SimpleNamespace(), logger_=logging.getLogger("test.form_sync_runner"))

        summary = runner._build_write_summary(
            "生产入库单",
            fetched=10,
            outcome=WriteOutcome(inserted=6, invalid=2, deduped=1),
        )

        self.assertEqual(
            summary,
            {
                "fetched": 10,
                "inserted": 6,
                "invalid": 2,
                "deduped": 1,
                "failed": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_form_sync_runner -v
```

Expected:

- 失败，提示 `FormSyncRunner` 没有 `_build_write_summary`

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/form_sync_runner.py
from src.core.write_outcome import WriteOutcome

def _build_write_summary(self, form_name: str, fetched: int, outcome: WriteOutcome) -> Dict[str, int]:
    deduped = outcome.deduped if form_name.strip() in self.owner.DEDUPLICATION_FORMS else 0
    invalid = outcome.invalid
    failed = max(0, fetched - invalid - deduped - outcome.inserted)
    return {
        "fetched": fetched,
        "inserted": outcome.inserted,
        "invalid": invalid,
        "deduped": deduped,
        "failed": failed,
    }

def insert_database_data(self, form_name: str, data: List[Dict], db_manager=None) -> WriteOutcome:
    manager = db_manager or mysql_manager
    method_name = self.owner.INSERT_METHOD_MAP.get(form_name)
    if method_name:
        try:
            return manager.execute_writer_with_outcome(method_name, data)
        except KeyError as exc:
            self.logger.error("Writer 映射无效: form=%s, method=%s, error=%s", form_name, method_name, exc)
            return WriteOutcome(failed=len(data))
    if form_name == "科目余额表":
        inserted = manager.insert_generic_data("GL_RPT_AccountBalance", data)
        return WriteOutcome.from_insert_count(inserted)
    self.logger.error("未知的表单类型或未配置插入方法: %s", form_name)
    return WriteOutcome(failed=len(data))
```

```python
# src/core/form_sync_runner.py inside sync_single_form()
            total_invalid_ref = [0]
            total_deduped_ref = [0]

            def insert_worker() -> None:
                while True:
                    page_data = data_queue.get()
                    if page_data is None:
                        data_queue.task_done()
                        break
                    try:
                        outcome = self.insert_database_data(form_name, page_data, db_manager=local_db)
                        total_inserted_ref[0] += outcome.inserted
                        total_invalid_ref[0] += outcome.invalid
                        total_deduped_ref[0] += outcome.deduped
                        total_fetched_ref[0] += len(page_data)
                        self.owner._notify_progress(
                            f"[{form_name}] 已同步 {total_inserted_ref[0]} 条数据...",
                            60,
                        )
                    except Exception as exc:
                        self.logger.error("[%s] 异步插入数据库失败: %s", form_name, exc)
                        insert_errors.append(exc)
                    finally:
                        data_queue.task_done()

            elif all_rows_buffer:
                outcome = self.insert_database_data(form_name, all_rows_buffer, db_manager=local_db)
                total_inserted_ref[0] = outcome.inserted
                total_invalid_ref[0] = outcome.invalid
                total_deduped_ref[0] = outcome.deduped
                self.owner._notify_progress(f"[{form_name}] 批量写入完成，共 {outcome.inserted} 条", 75)

            summary = self._build_write_summary(
                form_name,
                fetched=record_count,
                outcome=WriteOutcome(
                    inserted=inserted_count,
                    invalid=total_invalid_ref[0],
                    deduped=total_deduped_ref[0],
                ),
            )
            if summary["invalid"] > 0:
                self.logger.warning("[%s] 无效记录跳过: %s 条", form_name, summary["invalid"])
            if summary["deduped"] > 0:
                self.logger.info("[%s] 去重跳过: %s 条", form_name, summary["deduped"])
            if summary["failed"] > 0:
                self.logger.warning("[%s] 写库失败: %s 条", form_name, summary["failed"])

            return {
                "status": SUCCESS_STATUS,
                "message": f"成功同步 {inserted_count} 条记录",
                "record_count": inserted_count,
                "fetched": summary["fetched"],
                "invalid": summary["invalid"],
                "deduped": summary["deduped"],
                "failed": summary["failed"],
                "inserted": inserted_count,
                "updated": 0,
                "duration": duration,
                "timing": {
                    "filter": round(filter_duration, 3),
                    "query": round(query_duration, 3),
                    "insert": round(insert_duration, 3),
                },
            }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_form_sync_runner -v
```

Expected:

- 测试为 `ok`
- 后续 `FormSyncRunner` 已具备输出 `fetched/invalid/deduped/failed` 的基础

- [ ] **Step 5: Commit**

```bash
git add src/core/form_sync_runner.py tests/test_form_sync_runner.py
git commit -m "fix: separate invalid and failed sync counts"
```

## Task 4: Guard Shutdown Scheduling and GUI Signal Emission

**Files:**
- Modify: `src/core/data_sync.py`
- Modify: `src/core/scheduler.py`
- Modify: `src/utils/kingdee_sync_tool.py`
- Modify: `src/gui/logging_utils.py`
- Test: `tests/test_data_sync_shutdown.py`
- Test: `tests/test_gui_logging_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_data_sync_shutdown.py
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.core.data_sync import DataSyncManager, SyncStatus, SyncType
from src.core.scheduler import AutoSyncScheduler, SchedulerStatus


class DataSyncShutdownTests(unittest.TestCase):
    def test_sync_data_short_circuits_when_shutdown_requested(self) -> None:
        manager = DataSyncManager()
        manager._check_connections = Mock(side_effect=AssertionError("should not reach connection checks"))
        manager.request_shutdown("application_exit")

        result = manager.sync_data(["销售订单"], SyncType.INCREMENTAL)

        self.assertEqual(result["status"], SyncStatus.FAILED_ABNORMAL_EXIT.value)
        self.assertIn("application_exit", result["message"])

    def test_scheduler_skips_execute_when_manager_is_shutting_down(self) -> None:
        scheduler = AutoSyncScheduler()
        scheduler.status = SchedulerStatus.RUNNING
        scheduler.sync_forms = ["销售订单"]
        scheduler.sync_type = SyncType.INCREMENTAL

        with patch("src.core.scheduler.sync_manager") as mock_sync_manager:
            mock_sync_manager.is_shutdown_requested.return_value = True
            scheduler._execute_sync()

        mock_sync_manager.sync_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

```python
# tests/test_gui_logging_utils.py
from __future__ import annotations

import logging
import unittest

from src.gui.logging_utils import GuiLogHandler


class BrokenSignalEmitter:
    class BrokenSignal:
        def emit(self, *_args, **_kwargs) -> None:
            raise RuntimeError("Signal source has been deleted")

    text_written = BrokenSignal()


class GuiLogHandlerTests(unittest.TestCase):
    def test_emit_swallows_deleted_signal_source_runtimeerror(self) -> None:
        handler = GuiLogHandler(BrokenSignalEmitter())
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)

        handler.emit(record)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_data_sync_shutdown tests.test_gui_logging_utils -v
```

Expected:

- `DataSyncManager` 没有 `request_shutdown()` / `is_shutdown_requested()`
- `scheduler._execute_sync()` 仍会继续执行
- `GuiLogHandler.emit()` 抛出 `RuntimeError: Signal source has been deleted`

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/data_sync.py inside DataSyncManager.__init__()
        self._shutdown_requested = threading.Event()
        self._shutdown_reason = ""

def request_shutdown(self, reason: str = "application_exit") -> None:
    self._shutdown_reason = reason
    self._shutdown_requested.set()

def clear_shutdown(self) -> None:
    self._shutdown_reason = ""
    self._shutdown_requested.clear()

def is_shutdown_requested(self) -> bool:
    return self._shutdown_requested.is_set()
```

```python
# src/core/data_sync.py at the top of sync_data()
        if self.is_shutdown_requested():
            message = f"同步任务拒绝启动: {self._shutdown_reason or 'shutdown requested'}"
            return {
                "status": SyncStatus.FAILED_ABNORMAL_EXIT.value,
                "message": message,
                "total_records": 0,
                "start_time": start_time,
                "end_time": start_time,
                "duration": 0,
                "details": {},
            }
```

```python
# src/core/data_sync.py before each new grouped dispatch
            for _, group in sorted(grouped_forms.items(), key=lambda item: item[0]):
                if self.is_shutdown_requested():
                    final_status = SyncStatus.FAILED_ABNORMAL_EXIT
                    final_message = (
                        f"同步在关闭过程中停止调度新任务: {self._shutdown_reason or 'shutdown requested'}"
                    )
                    break
```

```python
# src/core/scheduler.py inside _execute_sync()
        if self.status != SchedulerStatus.RUNNING:
            return
        if sync_manager.is_shutdown_requested():
            logger.info("检测到应用正在退出，跳过新的定时同步任务")
            return
```

```python
# src/utils/kingdee_sync_tool.py inside cleanup_and_exit()
        from src.core.data_sync import sync_manager

        sync_manager.request_shutdown("application_exit")

        if auto_scheduler.status.value != "stopped":
            auto_scheduler.stop()
            logger.info("自动同步调度器已停止")
```

```python
# src/gui/logging_utils.py
class GuiLogHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        level = record.levelname
        emitter = self.signal_emitter
        if emitter is None:
            return
        try:
            emitter.text_written.emit(msg, level)
        except RuntimeError as exc:
            if "Signal source has been deleted" in str(exc):
                return
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_data_sync_shutdown tests.test_gui_logging_utils -v
```

Expected:

- 3 个测试均为 `ok`
- scheduler 日志允许输出 `检测到应用正在退出，跳过新的定时同步任务`

- [ ] **Step 5: Commit**

```bash
git add src/core/data_sync.py src/core/scheduler.py src/utils/kingdee_sync_tool.py src/gui/logging_utils.py tests/test_data_sync_shutdown.py tests/test_gui_logging_utils.py
git commit -m "fix: guard shutdown task scheduling"
```

## Task 5: Run Focused Regression Suite

**Files:**
- Modify: `docs/superpowers/plans/2026-04-20-kingdee-sync-error-chain.md`（仅在执行过程中勾选复选框，不改技术内容）

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
python3 -m unittest \
  tests.test_kingdee_api \
  tests.test_prd_instock_write_validation \
  tests.test_form_sync_runner \
  tests.test_data_sync_shutdown \
  tests.test_gui_logging_utils -v
```

Expected:

- 所有测试为 `ok`
- 不出现新的 `ImportError` 或接口签名不匹配错误

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
python3 -m ruff check \
  src/core/kingdee_api.py \
  src/core/write_outcome.py \
  src/core/mysql_manager.py \
  src/core/upsert_engine_sqlserver.py \
  src/core/form_sync_runner.py \
  src/core/data_sync.py \
  src/core/scheduler.py \
  src/utils/kingdee_sync_tool.py \
  src/gui/logging_utils.py \
  tests/test_kingdee_api.py \
  tests/test_prd_instock_write_validation.py \
  tests/test_form_sync_runner.py \
  tests/test_data_sync_shutdown.py \
  tests/test_gui_logging_utils.py
```

Expected:

- 输出 `All checks passed!`

- [ ] **Step 3: Smoke-check acceptance criteria in logs**

人工确认：

- 不再把 “会话信息已丢失，请重新登录” 当成业务记录
- `prd_instock` 空 `FBILLNO` 记录计入 `invalid`，不会拖垮整批写入
- 退出后不再出现 `cannot schedule new futures after interpreter shutdown`
- 退出后不再出现 `Signal source has been deleted`
- 日志能区分 `去重跳过`、`无效记录跳过`、`写库失败`

## Self-Review

### Spec coverage

- 查询入口收紧与会话重登：Task 1
- `prd_instock` 严格校验与 SQL Server staging 过滤：Task 2
- `fetched/invalid/deduped/inserted/failed` 统计口径：Task 3
- shutdown/调度/GUI 信号防护：Task 4
- 回归验证与验收：Task 5

无 spec 漏项。

### Placeholder scan

- 已避免 `TODO`、`TBD`、`implement later`
- 每个代码步骤都给出了实际代码
- 每个测试步骤都给出了实际命令和预期结果

### Type consistency

- `WriteOutcome` 和 `execute_writer_with_outcome()` 在 Task 2 定义，Task 3 才开始消费
- `request_shutdown()` / `is_shutdown_requested()` 在 Task 4 定义并在同一任务里被 `scheduler` 和 `cleanup_and_exit()` 使用
- `FormSyncRunner._build_write_summary()` 在 Task 3 定义并在同一任务内接入主流程

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-20-kingdee-sync-error-chain.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 我为每个任务派发一个新的子代理，任务间逐步 review，迭代更快

**2. Inline Execution** - 在当前会话里按计划执行，使用 executing-plans 批量推进并在检查点停下

Which approach?
