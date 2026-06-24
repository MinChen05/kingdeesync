from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from src.services.task_service import TaskService


def make_service() -> tuple[TaskService, SimpleNamespace, SimpleNamespace]:
    config = SimpleNamespace(
        get_table_mapping=Mock(
            return_value={
                "物料基础资料": "T_BD_Material",
                "客户资料": "T_BD_Customer",
                "销售订单": "T_SAL_SaleOrder",
            }
        ),
        get_sync_config=Mock(return_value={"default_forms": ["物料基础资料", "销售订单"], "sync_type": "incremental"}),
        get_increment_field=Mock(side_effect=lambda form: {"销售订单": "FDate"}.get(form, "FModifyDate")),
        set_increment_field=Mock(),
        save_sync_preferences=Mock(),
    )
    history = SimpleNamespace(
        get_history=Mock(
            return_value=(
                [
                    {
                        "task_name": "销售订单同步",
                        "form_name": "销售订单",
                        "status": "failed",
                        "start_time": "2026-06-23 10:00:00",
                        "duration_seconds": 45,
                        "record_count": 128,
                        "error_message": "字段缺失",
                    },
                    {
                        "task_name": "物料基础资料同步",
                        "form_name": "物料基础资料",
                        "status": "success",
                        "start_time": "2026-06-23 09:00:00",
                        "duration_seconds": 12,
                        "record_count": 8542,
                    },
                ],
                2,
            )
        )
    )
    return TaskService(config_manager=config, history_manager=history), config, history


def make_service_with_sync() -> tuple[TaskService, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    service, config, history = make_service()
    sync = SimpleNamespace(sync_data=Mock(return_value={"status": "success", "message": "ok"}))
    service.sync_service = sync
    return service, config, history, sync


def make_service_with_config(
    *,
    table_mapping: dict[str, str] | None = None,
    default_forms: list[str] | None = None,
    increment_fields: dict[str, str] | None = None,
) -> tuple[TaskService, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    service, config, history, sync = make_service_with_sync()
    if table_mapping is not None:
        config.get_table_mapping.return_value = table_mapping
    if default_forms is not None:
        config.get_sync_config.return_value = {"default_forms": default_forms, "sync_type": "incremental"}
    if increment_fields is not None:
        config.get_increment_field.side_effect = lambda form: increment_fields.get(form, "")
    return service, config, history, sync


def test_task_service_builds_tasks_from_config_and_history() -> None:
    service, config, history = make_service()

    tasks, total = service.get_tasks()

    assert total == 3
    assert [task["task_name"] for task in tasks] == ["物料基础资料同步", "销售订单同步", "客户资料同步"]
    assert tasks[0]["form_name"] == "T_BD_Material"
    assert tasks[0]["status"] == "enabled"
    assert tasks[0]["increment_field"] == "FModifyDate"
    assert tasks[0]["last_run"] == "2026-06-23 09:00:00"
    assert tasks[0]["success_rate"] == "100%"
    assert tasks[1]["status"] == "failed"
    assert tasks[1]["last_error_message"] == "字段缺失"
    assert tasks[2]["status"] == "paused"
    config.get_table_mapping.assert_called_once()
    history.get_history.assert_called_once()


def test_task_service_reads_increment_field_by_target_table_before_form_name() -> None:
    service, config, _ = make_service()
    config.get_increment_field.side_effect = lambda key: {"T_SAL_SaleOrder": "FModifyDate", "销售订单": "FDate"}.get(key, "")

    tasks, _ = service.get_tasks()

    sales_order = next(task for task in tasks if task["task_name"] == "销售订单同步")
    assert sales_order["increment_field"] == "FModifyDate"


def test_task_service_filters_tasks() -> None:
    service, _, _ = make_service()

    tasks, total = service.get_tasks(filters={"status": "启用中", "keyword": "物料"})

    assert total == 1
    assert tasks[0]["task_name"] == "物料基础资料同步"


def test_task_service_paginates_filtered_tasks() -> None:
    service, _, _ = make_service()

    tasks, total = service.get_tasks(page=2, page_size=1)

    assert total == 3
    assert len(tasks) == 1
    assert tasks[0]["task_name"] == "销售订单同步"


def test_task_service_stats_are_derived_from_real_tasks() -> None:
    service, _, _ = make_service()

    stats = service.get_task_stats()

    assert stats["enabled"] == 1
    assert stats["paused"] == 1
    assert stats["retry"] == 1
    assert stats["executed_today"] == 3
    assert stats["total"] == 3


def test_task_service_enable_pause_and_batch_enable_update_default_forms_only() -> None:
    service, config, _ = make_service()

    assert service.pause_task("销售订单同步") == 1
    config.save_sync_preferences.assert_called_with(["物料基础资料"], "incremental")

    config.save_sync_preferences.reset_mock()
    assert service.enable_task("客户资料同步") == 1
    config.save_sync_preferences.assert_called_with(["客户资料", "物料基础资料", "销售订单"], "incremental")

    config.save_sync_preferences.reset_mock()
    assert service.batch_enable_tasks() == 3
    config.save_sync_preferences.assert_called_with(["客户资料", "物料基础资料", "销售订单"], "incremental")


def test_task_service_create_and_edit_are_read_only_stage_placeholders() -> None:
    service, _, _ = make_service()

    assert service.open_create_task() is True
    assert service.edit_task("物料基础资料同步") is True
    assert service.last_action == "edit:物料基础资料同步"


def test_task_service_exposes_form_options_and_task_editor_data() -> None:
    service, _, _ = make_service()

    assert service.get_form_options() == [
        ("客户资料", "T_BD_Customer"),
        ("物料基础资料", "T_BD_Material"),
        ("销售订单", "T_SAL_SaleOrder"),
    ]

    editor_data = service.get_task_editor_data("销售订单同步")

    assert editor_data["form_name"] == "销售订单"
    assert editor_data["target_table"] == "T_SAL_SaleOrder"
    assert editor_data["sync_mode"] == "incremental"
    assert editor_data["enabled"] is True
    assert editor_data["increment_field"] == "FModifyDate"


def test_task_service_save_task_updates_only_config_preferences() -> None:
    service, config, _ = make_service()

    result = service.save_task(
        {
            "form_name": "客户资料",
            "sync_mode": "full",
            "enabled": True,
            "increment_field": "FModifyTime",
        }
    )

    assert result == {"saved": True, "form_name": "客户资料"}
    config.save_sync_preferences.assert_called_with(["客户资料", "物料基础资料", "销售订单"], "complete")
    config.set_increment_field.assert_called_once_with("T_BD_Customer", "FModifyTime")


def test_task_service_save_task_accepts_complete_sync_preference() -> None:
    service, config, _ = make_service()

    result = service.save_task(
        {
            "form_name": "客户资料",
            "sync_mode": "complete",
            "enabled": True,
            "increment_field": "FModifyTime",
        }
    )

    assert result == {"saved": True, "form_name": "客户资料"}
    config.save_sync_preferences.assert_called_with(["客户资料", "物料基础资料", "销售订单"], "complete")


def test_task_service_complete_sync_mode_displays_as_complete_sync() -> None:
    service, config, _ = make_service()
    config.get_sync_config.return_value = {"default_forms": ["物料基础资料"], "sync_type": "complete"}

    tasks, _ = service.get_tasks()

    task = next(item for item in tasks if item["task_name"] == "物料基础资料同步")
    assert task["sync_mode"] == "完全同步"


def test_task_service_legacy_full_sync_mode_displays_as_complete_sync_for_ui_compatibility() -> None:
    service, config, _ = make_service()
    config.get_sync_config.return_value = {"default_forms": ["物料基础资料"], "sync_type": "full"}

    tasks, _ = service.get_tasks(filters={"sync_mode": "完全同步"})

    assert len(tasks) == 3
    assert {task["sync_mode"] for task in tasks} == {"完全同步"}


def test_task_service_run_task_calls_sync_service_for_single_form() -> None:
    from src.core.data_sync import SyncType

    service, _, _, sync = make_service_with_sync()

    result = service.run_task("销售订单同步")

    sync.sync_data.assert_called_once()
    assert sync.sync_data.call_args.args == (["销售订单"], SyncType.INCREMENTAL)
    assert "progress_callback" in sync.sync_data.call_args.kwargs
    assert result == {"status": "success", "message": "ok"}
    assert service.last_action == "run:销售订单同步"


def test_task_service_run_task_uses_complete_sync_type_for_complete_config() -> None:
    from src.core.data_sync import SyncType

    service, config, _, sync = make_service_with_sync()
    config.get_sync_config.return_value = {"default_forms": ["销售订单"], "sync_type": "complete"}

    service.run_task("销售订单同步")

    sync.sync_data.assert_called_once()
    assert sync.sync_data.call_args.args == (["销售订单"], SyncType.COMPLETE)


def test_task_service_run_task_migrates_legacy_full_config_to_complete_sync_type() -> None:
    from src.core.data_sync import SyncType

    service, config, _, sync = make_service_with_sync()
    config.get_sync_config.return_value = {"default_forms": ["销售订单"], "sync_type": "full"}

    service.run_task("销售订单同步")

    sync.sync_data.assert_called_once()
    assert sync.sync_data.call_args.args == (["销售订单"], SyncType.COMPLETE)


def test_task_service_run_task_records_result_summary_and_updates_task_snapshot() -> None:
    service, _, _, sync = make_service_with_sync()
    sync.sync_data.return_value = {
        "status": "success",
        "message": "OK",
        "total_records": 1234,
        "duration": 2.5,
    }

    service.run_task("销售订单同步")

    audit = service.get_latest_operation_audit()
    assert audit["status"] == "success"
    assert audit["summary"] == "立即运行：销售订单同步，成功，写入 1,234 行，耗时 2.5 秒"
    assert audit["detail"] == "销售订单同步：状态 成功；写入 1,234 行；耗时 2.5 秒；OK"

    tasks, _ = service.get_tasks()
    task = next(item for item in tasks if item["task_name"] == "销售订单同步")
    assert task["status"] == "success"
    assert task["last_run"] != "2026-06-23 10:00:00"
    assert task["record_count"] == 1234
    assert task["duration_seconds"] == 2.5
    assert task["success_rate"] == "100%"


def test_task_service_marks_task_running_during_sync_and_restores_result() -> None:
    service, _, _, sync = make_service_with_sync()
    observed: list[dict[str, Any]] = []
    observed_audit: list[dict[str, str]] = []

    def sync_side_effect(_forms, _sync_type, *, progress_callback=None):
        tasks, _ = service.get_tasks()
        observed.append(next(item for item in tasks if item["task_name"] == "销售订单同步"))
        observed_audit.append(service.get_latest_operation_audit())
        return {"status": "success", "message": "OK", "total_records": 42, "duration": 1.5}

    sync.sync_data.side_effect = sync_side_effect

    service.run_task("销售订单同步")

    assert observed[0]["status"] == "running"
    assert observed[0]["success_rate"] == "--"
    assert observed_audit[0]["status"] == "running"

    tasks, _ = service.get_tasks()
    task = next(item for item in tasks if item["task_name"] == "销售订单同步")
    assert task["status"] == "success"
    assert task["record_count"] == 42
    assert task["duration_seconds"] == 1.5
    assert service.get_latest_operation_audit()["status"] == "success"


def test_task_service_run_task_forwards_progress_callback_and_updates_running_audit() -> None:
    from src.core.data_sync import SyncType

    service, _, _, sync = make_service_with_sync()
    progress_events: list[tuple[str, int]] = []
    observed_audit: list[dict[str, str]] = []

    def sync_side_effect(_forms, _sync_type, *, progress_callback=None):
        progress_callback("正在拉取数据", 37)
        progress_events.append(("正在拉取数据", 37))
        observed_audit.append(service.get_latest_operation_audit())
        return {"status": "success"}

    sync.sync_data.side_effect = sync_side_effect

    service.run_task("销售订单同步", progress_callback=lambda message, percent: progress_events.append((message, percent)))

    sync.sync_data.assert_called_once()
    assert sync.sync_data.call_args.kwargs["progress_callback"] is not None
    assert sync.sync_data.call_args.args == (["销售订单"], SyncType.INCREMENTAL)
    assert progress_events == [("正在拉取数据", 37), ("正在拉取数据", 37)]
    assert observed_audit[0]["status"] == "running"
    assert observed_audit[0]["summary"] == "立即运行：销售订单同步，37%，正在拉取数据"
    assert observed_audit[0]["detail"] == "销售订单同步：正在拉取数据，37%"


def test_task_service_progress_updates_task_snapshot_for_detail_panel() -> None:
    service, _, _, sync = make_service_with_sync()
    observed: list[dict[str, Any]] = []

    def sync_side_effect(_forms, _sync_type, *, progress_callback=None):
        progress_callback("正在拉取数据", 37)
        tasks, _ = service.get_tasks()
        observed.append(next(item for item in tasks if item["task_name"] == "销售订单同步"))
        return {"status": "success", "total_records": 42, "duration": 1.5}

    sync.sync_data.side_effect = sync_side_effect

    service.run_task("销售订单同步")

    assert observed[0]["status"] == "running"
    assert observed[0]["progress_stage"] == "正在拉取数据"
    assert observed[0]["progress_percent"] == 37
    assert observed[0]["progress_updated_at"] != "--"

    tasks, _ = service.get_tasks()
    task = next(item for item in tasks if item["task_name"] == "销售订单同步")
    assert task["status"] == "success"
    assert task["record_count"] == 42
    assert task["duration_seconds"] == 1.5


def test_task_service_batch_run_summary_includes_result_totals_with_fallbacks() -> None:
    service, _, _, sync = make_service_with_sync()
    sync.sync_data.side_effect = [
        {"status": "success", "inserted": 100, "updated": 20, "duration_seconds": 3, "message": "done"},
        {"status": "failed", "total_records": 0, "duration": 1.2, "message": "写入失败"},
    ]

    result = service.run_tasks(["物料基础资料同步", "销售订单同步"])

    assert result["requested"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["errors"] == [{"task_name": "销售订单同步", "error": "写入失败"}]
    audit = service.get_latest_operation_audit()
    assert audit["status"] == "failed"
    assert audit["summary"] == "批量运行：成功 1/2，失败 1，写入 120 行，耗时 4.2 秒"
    assert "销售订单同步：写入失败" in audit["detail"]


def test_task_service_batch_run_marks_each_task_running_during_sync() -> None:
    service, _, _, sync = make_service_with_sync()
    observed_statuses: list[tuple[str, str]] = []

    def sync_side_effect(forms, _sync_type, *, progress_callback=None):
        form_name = forms[0]
        tasks, _ = service.get_tasks()
        task = next(item for item in tasks if item["form_key"] == form_name)
        observed_statuses.append((task["task_name"], task["status"]))
        return {"status": "success"}

    sync.sync_data.side_effect = sync_side_effect

    service.run_tasks(["物料基础资料同步", "销售订单同步"])

    assert observed_statuses == [("物料基础资料同步", "running"), ("销售订单同步", "running")]
    assert service.get_latest_operation_audit()["operation"] == "批量运行"
    assert service.get_latest_operation_audit()["status"] == "success"


def test_task_service_batch_run_forwards_progress_for_each_task() -> None:
    service, _, _, sync = make_service_with_sync()
    progress_events: list[tuple[str, int]] = []
    observed_audit: list[str] = []

    def sync_side_effect(forms, _sync_type, *, progress_callback=None):
        progress_callback(f"{forms[0]} 字段转换", 66)
        observed_audit.append(service.get_latest_operation_audit()["summary"])
        return {"status": "success"}

    sync.sync_data.side_effect = sync_side_effect

    service.run_tasks(
        ["物料基础资料同步", "销售订单同步"],
        progress_callback=lambda message, percent: progress_events.append((message, percent)),
    )

    assert progress_events == [("物料基础资料 字段转换", 66), ("销售订单 字段转换", 66)]
    assert observed_audit == [
        "立即运行：物料基础资料同步，66%，物料基础资料 字段转换",
        "立即运行：销售订单同步，66%，销售订单 字段转换",
    ]
    assert service.get_latest_operation_audit()["operation"] == "批量运行"


def test_task_service_cancel_task_records_unsupported_when_sync_service_cannot_cancel() -> None:
    service, _, _, sync = make_service_with_sync()

    result = service.cancel_task("销售订单同步")

    assert result == {
        "cancelled": False,
        "supported": False,
        "message": "当前同步任务暂不支持中止",
        "task_name": "销售订单同步",
    }
    assert not hasattr(sync, "cancel_task")
    audit = service.get_latest_operation_audit()
    assert audit["operation"] == "中止任务"
    assert audit["status"] == "warning"
    assert audit["summary"] == "中止任务：销售订单同步，当前同步任务暂不支持中止"
    assert audit["detail"] == "销售订单同步：当前同步任务暂不支持中止"


def test_task_service_cancel_task_delegates_when_sync_service_supports_cancel() -> None:
    service, _, _, sync = make_service_with_sync()
    sync.cancel_sync = Mock()

    result = service.cancel_task("销售订单同步")

    sync.cancel_sync.assert_called_once_with()
    assert result == {
        "cancelled": True,
        "supported": True,
        "message": "已发送中止请求",
        "task_name": "销售订单同步",
    }
    audit = service.get_latest_operation_audit()
    assert audit["operation"] == "中止任务"
    assert audit["status"] == "success"
    assert audit["summary"] == "中止任务：销售订单同步，已发送中止请求"


def test_task_service_run_task_raises_for_unknown_task() -> None:
    service, _, _, sync = make_service_with_sync()

    try:
        service.run_task("不存在同步")
    except ValueError as exc:
        assert "未找到任务" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
    sync.sync_data.assert_not_called()


def test_task_service_batch_pause_and_run_tasks_use_existing_paths() -> None:
    from src.core.data_sync import SyncType

    service, config, _, sync = make_service_with_sync()

    assert service.pause_tasks(["销售订单同步", "物料基础资料同步"]) == 2
    config.save_sync_preferences.assert_called_with([], "incremental")

    result = service.run_tasks(["物料基础资料同步", "销售订单同步"])

    assert result == {
        "requested": 2,
        "succeeded": 2,
        "failed": 0,
        "errors": [],
        "total_records": 0,
        "duration_seconds": 0.0,
    }
    assert sync.sync_data.call_args_list[-2].args == (["物料基础资料"], SyncType.INCREMENTAL)
    assert sync.sync_data.call_args_list[-1].args == (["销售订单"], SyncType.INCREMENTAL)


def test_task_service_run_tasks_reports_failed_task_details() -> None:
    service, _, _, sync = make_service_with_sync()
    sync.sync_data.side_effect = [{"status": "success"}, RuntimeError("API 超时")]

    result = service.run_tasks(["物料基础资料同步", "销售订单同步"])

    assert result["requested"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["errors"] == [{"task_name": "销售订单同步", "error": "API 超时"}]


def test_task_service_records_latest_operation_audit() -> None:
    service, _, _, sync = make_service_with_sync()
    sync.sync_data.side_effect = [{"status": "success"}, RuntimeError("API 超时")]

    result = service.run_tasks(["物料基础资料同步", "销售订单同步"])
    audit = service.get_latest_operation_audit()

    assert result["failed"] == 1
    assert audit["operation"] == "批量运行"
    assert audit["status"] == "failed"
    assert audit["summary"] == "批量运行：成功 1/2，失败 1"
    assert audit["detail"] == "销售订单同步：API 超时"
    assert audit["timestamp"]


def test_task_service_keeps_recent_operation_history_and_can_clear_view() -> None:
    service, _, _, sync = make_service_with_sync()

    service.open_create_task()
    service.edit_task("物料基础资料同步")
    sync.sync_data.side_effect = RuntimeError("API 超时")
    try:
        service.run_task("销售订单同步")
    except RuntimeError:
        pass

    history = service.get_operation_history(limit=2)

    assert [item["operation"] for item in history] == ["立即运行", "编辑任务"]
    assert history[0]["status"] == "failed"
    assert history[0]["detail"] == "销售订单同步：API 超时"
    history[0]["summary"] = "mutated"
    assert service.get_latest_operation_audit()["summary"] != "mutated"

    service.clear_operation_history()

    assert service.get_operation_history() == []
    assert service.get_latest_operation_audit() == {}


def test_task_service_filters_operation_history_by_status_and_keyword() -> None:
    service, _, _, sync = make_service_with_sync()

    service.edit_task("物料基础资料同步")
    sync.sync_data.return_value = {"status": "success", "total_records": 12, "duration": 1}
    service.run_task("销售订单同步")
    sync.sync_data.side_effect = RuntimeError("API 超时")
    try:
        service.run_task("销售订单同步")
    except RuntimeError:
        pass

    failed_history = service.get_operation_history(limit=10, filters={"status": "失败", "keyword": "销售订单"})

    assert len(failed_history) == 1
    assert failed_history[0]["status"] == "failed"
    assert failed_history[0]["task_name"] == "销售订单同步"
    assert failed_history[0]["failure_reason"] == "API 超时"

    success_history = service.get_operation_history(limit=10, filters={"status": "成功", "keyword": "物料"})

    assert len(success_history) == 1
    assert success_history[0]["operation"] == "编辑任务"
    assert success_history[0]["summary"] == "编辑任务：物料基础资料同步"


def test_task_service_queries_operation_history_with_pagination_and_exports_report() -> None:
    service, _, _, sync = make_service_with_sync()

    service.edit_task("物料基础资料同步")
    sync.sync_data.return_value = {"status": "success", "total_records": 12, "duration": 1}
    service.run_task("销售订单同步")
    sync.sync_data.side_effect = RuntimeError("API 超时")
    try:
        service.run_task("销售订单同步")
    except RuntimeError:
        pass

    page = service.query_operation_history(page=2, page_size=1, filters={"keyword": "同步"})

    assert page["total"] == 3
    assert page["page"] == 2
    assert page["page_size"] == 1
    assert len(page["items"]) == 1
    assert page["items"][0]["summary"] == "立即运行：销售订单同步，成功，写入 12 行，耗时 1 秒"

    report = service.export_operation_history_report(filters={"status": "失败"})

    assert "任务运行历史报表" in report
    assert "筛选: 状态=失败" in report
    assert "立即运行失败：API 超时" in report
    assert "任务名称: 销售订单同步" in report
    assert "失败原因: API 超时" in report


def test_task_service_summarizes_operation_history_for_current_filters() -> None:
    service, _, _, sync = make_service_with_sync()

    service.edit_task("物料基础资料同步")
    sync.sync_data.return_value = {"status": "success", "total_records": 12, "duration": 2}
    service.run_task("销售订单同步")
    sync.sync_data.side_effect = RuntimeError("API 超时")
    try:
        service.run_task("销售订单同步")
    except RuntimeError:
        pass
    service._record_operation_audit(  # noqa: SLF001 - exercise public summary over an in-memory warning audit
        "立即运行",
        "warning",
        "立即运行：销售订单同步，警告",
        metadata={"task_name": "销售订单同步", "duration_seconds": 4},
    )

    summary = service.get_operation_history_summary(filters={"keyword": "同步"})

    assert summary == {
        "success": 1,
        "failed": 1,
        "warning": 1,
        "avg_duration": "3 秒",
        "total": 3,
    }

    empty = service.get_operation_history_summary(filters={"keyword": "不存在"})

    assert empty == {
        "success": 0,
        "failed": 0,
        "warning": 0,
        "avg_duration": "--",
        "total": 0,
    }


def test_task_service_run_task_records_traceable_run_detail() -> None:
    service, _, _, sync = make_service_with_sync()

    def sync_side_effect(_forms, _sync_type, *, progress_callback=None):
        progress_callback("正在拉取数据", 20)
        progress_callback("写入 SQL Server", 80)
        return {"status": "success", "total_records": 42, "duration": 1.5, "message": "OK"}

    sync.sync_data.side_effect = sync_side_effect

    service.run_task("销售订单同步")

    history = service.get_operation_history(limit=1)
    assert len(history) == 1
    record = history[0]
    assert record["operation"] == "立即运行"
    assert record["task_name"] == "销售订单同步"
    assert record["run_started_at"]
    assert record["run_finished_at"]
    assert record["final_status"] == "成功"
    assert record["record_count"] == 42
    assert record["duration_seconds"] == 1.5
    assert record["failure_reason"] == ""
    assert record["progress_summary"] == "20% 正在拉取数据；80% 写入 SQL Server"
    assert "开始时间:" in record["run_detail"]
    assert "结束时间:" in record["run_detail"]
    assert "最终状态: 成功" in record["run_detail"]
    assert "写入行数: 42" in record["run_detail"]
    assert "耗时: 1.5 秒" in record["run_detail"]
    assert "进度摘要: 20% 正在拉取数据；80% 写入 SQL Server" in record["run_detail"]


def test_task_service_run_task_exposes_traceable_detail_on_task_snapshot() -> None:
    service, _, _, sync = make_service_with_sync()

    def sync_side_effect(_forms, _sync_type, *, progress_callback=None):
        progress_callback("写入 SQL Server", 80)
        return {"status": "success", "total_records": 42, "duration": 1.5}

    sync.sync_data.side_effect = sync_side_effect

    service.run_task("销售订单同步")

    tasks, _ = service.get_tasks()
    task = next(item for item in tasks if item["task_name"] == "销售订单同步")
    assert task["run_started_at"]
    assert task["run_finished_at"]
    assert task["final_status"] == "成功"
    assert task["progress_summary"] == "80% 写入 SQL Server"
    assert "任务名称: 销售订单同步" in task["run_detail"]
    assert "写入行数: 42" in task["run_detail"]


def test_task_service_batch_run_records_traceable_run_detail() -> None:
    service, _, _, sync = make_service_with_sync()

    def sync_side_effect(forms, _sync_type, *, progress_callback=None):
        progress_callback(f"{forms[0]} 拉取数据", 30)
        if forms[0] == "销售订单":
            return {"status": "failed", "total_records": 0, "duration": 2.0, "message": "字段缺失"}
        return {"status": "success", "total_records": 100, "duration": 3.0, "message": "OK"}

    sync.sync_data.side_effect = sync_side_effect

    service.run_tasks(["物料基础资料同步", "销售订单同步"])

    record = service.get_operation_history(limit=1)[0]
    assert record["operation"] == "批量运行"
    assert record["task_name"] == "物料基础资料同步、销售订单同步"
    assert record["run_started_at"]
    assert record["run_finished_at"]
    assert record["final_status"] == "失败"
    assert record["record_count"] == 100
    assert record["duration_seconds"] == 5.0
    assert record["failure_reason"] == "销售订单同步：字段缺失"
    assert record["progress_summary"] == "物料基础资料同步：30% 物料基础资料 拉取数据；销售订单同步：30% 销售订单 拉取数据"
    assert "最终状态: 失败" in record["run_detail"]
    assert "写入行数: 100" in record["run_detail"]
    assert "耗时: 5 秒" in record["run_detail"]
    assert "失败原因: 销售订单同步：字段缺失" in record["run_detail"]


def test_task_service_run_task_validates_enabled_mapping_and_increment_before_sync() -> None:
    service, _, _, sync = make_service_with_config(default_forms=["物料基础资料"], increment_fields={"销售订单": "FDate"})

    try:
        service.run_task("销售订单同步")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected validation error")

    assert "任务未启用" in message
    sync.sync_data.assert_not_called()
    audit = service.get_latest_operation_audit()
    assert audit["operation"] == "运行前校验"
    assert audit["status"] == "failed"
    assert audit["detail"] == "销售订单同步：任务未启用"


def test_task_service_run_task_allows_missing_increment_field_for_core_inference() -> None:
    service, _, _, sync = make_service_with_config(default_forms=["销售订单"], increment_fields={"销售订单": ""})

    result = service.run_task("销售订单同步")

    assert result["status"] == "success"
    sync.sync_data.assert_called_once()
    assert sync.sync_data.call_args.args[0] == ["销售订单"]


def test_task_service_run_task_validation_blocks_missing_mapping_only() -> None:
    service, _, _, sync = make_service_with_config(table_mapping={"销售订单": ""}, default_forms=["销售订单"], increment_fields={"销售订单": ""})

    try:
        service.run_task("销售订单同步")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected validation error")

    assert "缺少表单映射" in message
    assert "缺少增量字段配置" not in message
    sync.sync_data.assert_not_called()
    assert service.get_latest_operation_audit()["detail"] == "销售订单同步：缺少表单映射"


def test_task_service_batch_run_validation_reports_failures_without_sync_for_invalid_tasks() -> None:
    service, _, _, sync = make_service_with_config(default_forms=["物料基础资料"], increment_fields={"物料基础资料": "FModifyDate", "销售订单": "FDate"})

    result = service.run_tasks(["物料基础资料同步", "销售订单同步"])

    assert result["requested"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["errors"] == [{"task_name": "销售订单同步", "error": "任务未启用"}]
    sync.sync_data.assert_called_once()
    assert service.get_latest_operation_audit()["detail"] == "销售订单同步：任务未启用"
