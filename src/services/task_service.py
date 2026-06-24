"""Task-management service built from sync configuration and history."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from src.config.config_manager import config_manager
from src.core.data_sync import SyncType
from src.core.history_manager import history_manager
from src.services.sync_service import sync_service


def _first_value(record: Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _status_text(status: Any) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"running", "运行中"}:
        return "运行中"
    if normalized in {"enabled", "active", "success", "ok", "启用中"}:
        return "启用中"
    if normalized in {"paused", "disabled", "stopped", "pause", "已暂停"}:
        return "已暂停"
    if normalized in {"failed", "error", "failure", "danger", "失败"}:
        return "失败"
    return str(status or "--")


class TaskService:
    """Expose task list and first-stage task actions without touching SQL writers."""

    def __init__(
        self,
        *,
        config_manager=config_manager,
        history_manager=history_manager,
        sync_service=sync_service,
    ) -> None:
        self.config_manager = config_manager
        self.history_manager = history_manager
        self.sync_service = sync_service
        self.last_action = ""
        self._latest_operation_audit: dict[str, Any] = {}
        self._operation_history: list[dict[str, Any]] = []
        self._operation_history_limit = 50
        self._runtime_task_snapshots: dict[str, dict[str, Any]] = {}

    def get_latest_operation_audit(self) -> dict[str, Any]:
        return dict(self._latest_operation_audit)

    def get_operation_history(self, limit: int = 10, filters: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit or 10))
        filtered = self._filter_operation_history(self._operation_history, filters or {})
        return [dict(item) for item in filtered[:safe_limit]]

    def query_operation_history(
        self,
        *,
        page: int = 1,
        page_size: int = 6,
        filters: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        safe_page = max(1, int(page or 1))
        safe_page_size = max(1, int(page_size or 6))
        filtered = self._filter_operation_history(self._operation_history, filters or {})
        total = len(filtered)
        start = (safe_page - 1) * safe_page_size
        return {
            "items": [dict(item) for item in filtered[start : start + safe_page_size]],
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
        }

    def export_operation_history_report(self, filters: Mapping[str, str] | None = None) -> str:
        safe_filters = dict(filters or {})
        records = self._filter_operation_history(self._operation_history, safe_filters)
        filter_text = self._format_operation_history_filter_text(safe_filters)
        lines = [
            "任务运行历史报表",
            f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"筛选: {filter_text}",
            f"总数: {len(records)}",
            "",
        ]
        for index, record in enumerate(records, start=1):
            lines.append(f"{index}. {record.get('summary') or '--'}")
            detail = str(record.get("run_detail") or record.get("detail") or "").strip()
            if detail:
                lines.append(detail)
            lines.append("")
        return "\n".join(lines).strip()

    def get_operation_history_summary(self, filters: Mapping[str, str] | None = None) -> dict[str, Any]:
        records = [
            record
            for record in self._filter_operation_history(self._operation_history, filters or {})
            if self._is_run_history_record(record)
        ]
        success = 0
        failed = 0
        warning = 0
        durations: list[float] = []
        for record in records:
            status_text = self._operation_status_text(record.get("status"))
            if status_text == "成功":
                success += 1
            elif status_text == "失败":
                failed += 1
            elif status_text == "警告":
                warning += 1
            duration = self._to_float(record.get("duration_seconds"))
            if duration > 0:
                durations.append(duration)
        return {
            "success": success,
            "failed": failed,
            "warning": warning,
            "avg_duration": self._format_duration(sum(durations) / len(durations)) if durations else "--",
            "total": len(records),
        }

    @staticmethod
    def _is_run_history_record(record: Mapping[str, Any]) -> bool:
        operation = str(record.get("operation") or "")
        return "运行" in operation or bool(record.get("run_detail") or record.get("run_started_at") or record.get("final_status"))

    def clear_operation_history(self) -> None:
        self._operation_history.clear()
        self._latest_operation_audit = {}

    def _filter_operation_history(
        self,
        history: list[dict[str, Any]],
        filters: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        status_filter = str(filters.get("status") or "").strip()
        keyword = str(filters.get("keyword") or "").strip().lower()
        result: list[dict[str, Any]] = []
        for item in history:
            if status_filter and self._operation_status_text(item.get("status")) != status_filter:
                continue
            if keyword:
                haystack = " ".join(
                    str(item.get(key) or "")
                    for key in (
                        "operation",
                        "summary",
                        "detail",
                        "run_detail",
                        "task_name",
                        "final_status",
                        "failure_reason",
                        "progress_summary",
                    )
                ).lower()
                if keyword not in haystack:
                    continue
            result.append(item)
        return result

    @staticmethod
    def _operation_status_text(status: Any) -> str:
        normalized = str(status or "").strip().lower()
        if normalized == "running":
            return "运行中"
        if normalized == "failed":
            return "失败"
        if normalized == "warning":
            return "警告"
        if normalized == "success":
            return "成功"
        return str(status or "--")

    @staticmethod
    def _format_operation_history_filter_text(filters: Mapping[str, str]) -> str:
        parts = []
        status = str(filters.get("status") or "").strip()
        keyword = str(filters.get("keyword") or "").strip()
        if status:
            parts.append(f"状态={status}")
        if keyword:
            parts.append(f"关键词={keyword}")
        return "，".join(parts) if parts else "全部"

    def get_tasks(
        self,
        filters: Mapping[str, str] | None = None,
        *,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[dict[str, Any]], int]:
        tasks = self._build_tasks()
        filtered = self._filter_tasks(tasks, filters or {})
        total = len(filtered)
        safe_page = max(1, int(page or 1))
        safe_page_size = max(1, int(page_size or 10))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return filtered[start:end], total

    def get_task_stats(self) -> dict[str, Any]:
        tasks = self._build_tasks()
        enabled = sum(1 for task in tasks if _status_text(task.get("status")) == "启用中")
        paused = sum(1 for task in tasks if _status_text(task.get("status")) == "已暂停")
        retry = sum(1 for task in tasks if _status_text(task.get("status")) == "失败")
        return {
            "enabled": enabled,
            "paused": paused,
            "executed_today": len(tasks),
            "retry": retry,
            "enabled_delta": "较昨日 --",
            "paused_delta": "较昨日 --",
            "executed_delta": "较昨日 --",
            "retry_delta": "较昨日 --",
            "total": len(tasks),
        }

    def open_create_task(self) -> bool:
        self.last_action = "create"
        self._record_operation_audit("新建任务", "success", "新建任务：已打开任务配置")
        return True

    def edit_task(self, task_name: str) -> bool:
        self.last_action = f"edit:{task_name}"
        self._record_operation_audit("编辑任务", "success", f"编辑任务：{task_name}")
        return True

    def get_form_options(self) -> list[tuple[str, str]]:
        return sorted(self._table_mapping().items())

    def get_task_editor_data(self, task_name: str) -> dict[str, Any]:
        form_name = self._form_name_from_task(task_name)
        if not form_name:
            return {}
        mapping = self._table_mapping()
        sync_config = self._sync_config()
        default_forms = set(sync_config.get("default_forms") or [])
        return {
            "form_name": form_name,
            "target_table": mapping.get(form_name, form_name),
            "sync_mode": self._normalize_sync_mode(sync_config.get("sync_type")),
            "enabled": not default_forms or form_name in default_forms,
            "increment_field": self._increment_field(form_name, mapping.get(form_name, form_name)),
        }

    def save_task(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        form_name = str(payload.get("form_name") or "").strip()
        if not form_name or form_name not in self._table_mapping():
            raise ValueError("请选择有效表单")
        sync_mode = self._normalize_sync_mode(payload.get("sync_mode") or self._sync_config().get("sync_type"))
        enabled = bool(payload.get("enabled"))
        increment_field = str(payload.get("increment_field") or "").strip()

        defaults = set(self._sync_config().get("default_forms") or [])
        if enabled:
            defaults.add(form_name)
        else:
            defaults.discard(form_name)
        self.config_manager.save_sync_preferences(sorted(defaults), sync_mode)
        if increment_field:
            self.config_manager.set_increment_field(self._target_table_key(form_name), increment_field)
        self.last_action = f"save:{form_name}"
        self._record_operation_audit("保存任务", "success", f"保存任务：{form_name}")
        return {"saved": True, "form_name": form_name}

    def enable_task(self, task_name: str) -> int:
        return self._set_task_enabled(task_name, True)

    def pause_task(self, task_name: str) -> int:
        return self._set_task_enabled(task_name, False)

    def cancel_task(self, task_name: str) -> dict[str, Any]:
        cancel_method = self._sync_cancel_method()
        if callable(cancel_method):
            cancel_method()
            self._record_operation_audit("中止任务", "success", f"中止任务：{task_name}，已发送中止请求", f"{task_name}：已发送中止请求")
            return {"cancelled": True, "supported": True, "message": "已发送中止请求", "task_name": task_name}

        message = "当前同步任务暂不支持中止"
        self._record_operation_audit("中止任务", "warning", f"中止任务：{task_name}，{message}", f"{task_name}：{message}")
        return {"cancelled": False, "supported": False, "message": message, "task_name": task_name}

    def pause_tasks(self, task_names: list[str]) -> int:
        forms = [self._form_name_from_task(name) for name in task_names]
        forms = [form for form in forms if form]
        if not forms:
            self._record_operation_audit("批量暂停", "warning", "批量暂停：未匹配到任务")
            return 0
        defaults = set(self._sync_config().get("default_forms") or [])
        for form in forms:
            defaults.discard(form)
        self._save_default_forms(sorted(defaults))
        self._record_operation_audit("批量暂停", "success", f"批量暂停：已暂停 {len(forms)} 个任务")
        return len(forms)

    def batch_enable_tasks(self) -> int:
        mapping = self._table_mapping()
        forms = sorted(mapping.keys())
        self._save_default_forms(forms)
        self._record_operation_audit("批量启用", "success", f"批量启用：已启用 {len(forms)} 个任务")
        return len(forms)

    def run_task(
        self,
        task_name: str,
        progress_callback: Callable[[str, int], None] | None = None,
        *,
        _trace_sink: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        form_name = self._form_name_from_task(task_name)
        if not form_name:
            raise ValueError(f"未找到任务：{task_name}")
        self._validate_task_before_run(task_name, form_name)
        self.last_action = f"run:{task_name}"
        run_trace = self._start_run_trace("立即运行", task_name)
        self._mark_task_running(task_name, form_name)
        try:
            result = self.sync_service.sync_data(
                [form_name],
                self._sync_type(),
                progress_callback=self._progress_callback_for_task(task_name, progress_callback, run_trace),
            )
            parsed = self._parse_sync_result(result)
            summary = self._build_run_summary("立即运行", task_name, parsed)
            detail = self._build_run_detail(task_name, parsed)
            metadata = self._build_run_trace_metadata(run_trace, parsed)
            self._update_runtime_task_snapshot(task_name, form_name, parsed, metadata)
            if _trace_sink is not None:
                _trace_sink.append(dict(metadata))
            self._record_operation_audit(
                "立即运行",
                parsed["audit_status"],
                summary,
                detail,
                metadata=metadata,
            )
            if parsed["audit_status"] == "failed":
                return result
            return result
        except Exception as exc:
            metadata = self._build_run_trace_metadata(
                run_trace,
                {
                    "audit_status": "failed",
                    "status_label": "失败",
                    "record_count": 0,
                    "duration_seconds": 0,
                    "message": str(exc),
                },
            )
            if _trace_sink is not None:
                _trace_sink.append(dict(metadata))
            self._record_operation_audit(
                "立即运行",
                "failed",
                f"立即运行失败：{exc}",
                f"{task_name}：{exc}",
                metadata=metadata,
            )
            raise

    def run_tasks(
        self,
        task_names: list[str],
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> dict[str, Any]:
        requested = len(task_names)
        succeeded = 0
        failed = 0
        total_records = 0
        total_duration = 0.0
        errors: list[dict[str, str]] = []
        batch_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        child_traces: list[dict[str, Any]] = []
        for task_name in task_names:
            try:
                result = self.run_task(task_name, progress_callback=progress_callback, _trace_sink=child_traces)
                parsed = self._parse_sync_result(result)
                total_records += int(parsed["record_count"] or 0)
                total_duration += float(parsed["duration_seconds"] or 0)
                if parsed["audit_status"] == "failed":
                    failed += 1
                    errors.append({"task_name": task_name, "error": parsed["message"] or "同步失败"})
                else:
                    succeeded += 1
            except Exception as exc:
                failed += 1
                errors.append({"task_name": task_name, "error": str(exc)})
        summary = f"批量运行：成功 {succeeded}/{requested}，失败 {failed}"
        if total_records or total_duration:
            summary = f"{summary}，写入 {self._format_count(total_records)} 行，耗时 {self._format_duration(total_duration)}"
        detail = "；".join(f"{error['task_name']}：{error['error']}" for error in errors)
        self._record_operation_audit(
            "批量运行",
            "failed" if failed else "success",
            summary,
            detail,
            metadata=self._build_batch_run_trace_metadata(
                task_names,
                batch_started_at,
                "失败" if failed else "成功",
                total_records,
                total_duration,
                detail,
                child_traces,
            ),
        )
        return {
            "requested": requested,
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
            "total_records": total_records,
            "duration_seconds": total_duration,
        }

    def _record_operation_audit(
        self,
        operation: str,
        status: str,
        summary: str,
        detail: str = "",
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._latest_operation_audit = {
            "operation": operation,
            "status": status,
            "summary": summary,
            "detail": detail,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if metadata:
            self._latest_operation_audit.update(dict(metadata))
        self._operation_history.insert(0, dict(self._latest_operation_audit))
        del self._operation_history[self._operation_history_limit :]

    def _sync_cancel_method(self):
        for method_name in ("cancel_task", "cancel_sync", "cancel"):
            method = getattr(self.sync_service, method_name, None)
            if callable(method):
                return method
        return None

    @staticmethod
    def _start_run_trace(operation: str, task_name: str) -> dict[str, Any]:
        return {
            "operation": operation,
            "task_name": task_name,
            "run_started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "progress_events": [],
        }

    @staticmethod
    def _append_run_progress(run_trace: dict[str, Any], message: str, percent: int) -> None:
        progress_events = run_trace.setdefault("progress_events", [])
        if isinstance(progress_events, list):
            progress_events.append({"message": message, "percent": percent})

    def _build_run_trace_metadata(self, run_trace: Mapping[str, Any], parsed: Mapping[str, Any]) -> dict[str, Any]:
        progress_summary = self._format_progress_summary(run_trace.get("progress_events"))
        audit_status = str(parsed.get("audit_status") or "")
        final_status = str(parsed.get("status_label") or ("成功" if audit_status == "success" else "失败"))
        record_count = parsed.get("record_count", 0)
        duration_seconds = parsed.get("duration_seconds", 0)
        failure_reason = str(parsed.get("message") or "") if audit_status == "failed" else ""
        metadata = {
            "task_name": str(run_trace.get("task_name") or ""),
            "run_started_at": str(run_trace.get("run_started_at") or ""),
            "run_finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "final_status": final_status,
            "record_count": record_count,
            "duration_seconds": duration_seconds,
            "failure_reason": failure_reason,
            "progress_summary": progress_summary,
        }
        metadata["run_detail"] = self._build_traceable_run_detail(metadata)
        return metadata

    def _build_batch_run_trace_metadata(
        self,
        task_names: list[str],
        run_started_at: str,
        final_status: str,
        record_count: int,
        duration_seconds: float,
        failure_reason: str,
        child_traces: list[dict[str, Any]],
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "task_name": "、".join(task_names),
            "run_started_at": run_started_at,
            "run_finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "final_status": final_status,
            "record_count": record_count,
            "duration_seconds": duration_seconds,
            "failure_reason": failure_reason,
            "progress_summary": self._format_batch_progress_summary(child_traces),
        }
        metadata["run_detail"] = self._build_traceable_run_detail(metadata)
        return metadata

    @staticmethod
    def _format_progress_summary(progress_events: Any) -> str:
        if not isinstance(progress_events, list) or not progress_events:
            return "无进度事件"
        parts = []
        for event in progress_events:
            if not isinstance(event, Mapping):
                continue
            percent = event.get("percent", 0)
            message = str(event.get("message") or "同步进行中")
            parts.append(f"{percent}% {message}")
        return "；".join(parts) if parts else "无进度事件"

    @staticmethod
    def _format_batch_progress_summary(child_traces: list[dict[str, Any]]) -> str:
        parts = []
        for trace in child_traces:
            task_name = str(trace.get("task_name") or "--")
            progress_summary = str(trace.get("progress_summary") or "")
            if progress_summary and progress_summary != "无进度事件":
                parts.append(f"{task_name}：{progress_summary}")
        return "；".join(parts) if parts else "无进度事件"

    def _build_traceable_run_detail(self, metadata: Mapping[str, Any]) -> str:
        lines = [
            f"任务名称: {metadata.get('task_name') or '--'}",
            f"开始时间: {metadata.get('run_started_at') or '--'}",
            f"结束时间: {metadata.get('run_finished_at') or '--'}",
            f"最终状态: {metadata.get('final_status') or '--'}",
            f"写入行数: {self._format_count(metadata.get('record_count', 0))}",
            f"耗时: {self._format_duration(metadata.get('duration_seconds', 0))}",
            f"失败原因: {metadata.get('failure_reason') or '--'}",
            f"进度摘要: {metadata.get('progress_summary') or '无进度事件'}",
        ]
        return "\n".join(lines)

    def _progress_callback_for_task(
        self,
        task_name: str,
        progress_callback: Callable[[str, int], None] | None,
        run_trace: dict[str, Any] | None = None,
    ) -> Callable[[str, int], None]:
        def handle_progress(message: str, percent: int) -> None:
            safe_percent = self._clamp_percent(percent)
            safe_message = str(message or "同步进行中")
            if run_trace is not None:
                self._append_run_progress(run_trace, safe_message, safe_percent)
            self._update_progress_task_snapshot(task_name, safe_message, safe_percent)
            self._set_transient_operation_audit(
                "立即运行",
                "running",
                f"立即运行：{task_name}，{safe_percent}%，{safe_message}",
                f"{task_name}：{safe_message}，{safe_percent}%",
            )
            if progress_callback is not None:
                progress_callback(safe_message, safe_percent)

        return handle_progress

    @staticmethod
    def _clamp_percent(value: Any) -> int:
        try:
            percent = int(float(str(value).replace("%", "")))
        except (TypeError, ValueError):
            return 0
        return max(0, min(percent, 100))

    def _set_transient_operation_audit(self, operation: str, status: str, summary: str, detail: str = "") -> None:
        self._latest_operation_audit = {
            "operation": operation,
            "status": status,
            "summary": summary,
            "detail": detail,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _mark_task_running(self, task_name: str, form_name: str) -> None:
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._runtime_task_snapshots[form_name] = {
            "status": "running",
            "last_run": now_text,
            "updated_at": now_text,
            "last_error_time": "",
            "last_error_message": "",
            "error_count": "0/3",
            "record_count": "",
            "duration_seconds": "",
            "success_rate": "--",
            "task_name": task_name,
            "progress_stage": "运行中",
            "progress_percent": 0,
            "progress_updated_at": now_text,
        }
        self._set_transient_operation_audit(
            "立即运行",
            "running",
            f"立即运行：{task_name}，运行中",
            f"{task_name}：运行中",
        )

    def _build_tasks(self) -> list[dict[str, Any]]:
        mapping = self._table_mapping()
        if not mapping:
            return []
        sync_config = self._sync_config()
        default_forms = set(sync_config.get("default_forms") or [])
        history_by_form = self._latest_history_by_form()
        form_names = sorted(mapping.keys(), key=lambda name: (name not in default_forms, name))

        tasks: list[dict[str, Any]] = []
        for index, form_name in enumerate(form_names, start=1):
            history = history_by_form.get(form_name, {})
            enabled = not default_forms or form_name in default_forms
            status = "failed" if str(history.get("status", "")).lower() in {"failed", "failure", "error"} else (
                "enabled" if enabled else "paused"
            )
            duration = _first_value(history, "duration_seconds", "duration", default="")
            record_count = _first_value(history, "record_count", "total_records", "rows", default="")
            task = {
                    "task_id": f"config_task_{index:03d}",
                    "task_name": f"{form_name}同步",
                    "form_key": form_name,
                    "form_name": mapping.get(form_name) or form_name,
                    "sync_mode": self._sync_mode_label(sync_config.get("sync_type")),
                    "schedule": "按同步执行配置",
                    "status": status,
                    "last_run": _first_value(history, "start_time", "end_time", "created_at", default="--"),
                    "success_rate": self._success_rate(history),
                    "created_at": "--",
                    "creator": "配置文件",
                    "updated_at": _first_value(history, "end_time", "start_time", default="--"),
                    "scope": form_name,
                    "increment_field": self._increment_field(form_name, mapping.get(form_name, form_name)),
                    "target_table": mapping.get(form_name) or form_name,
                    "retry_policy": "沿用同步策略配置",
                    "last_error_time": _first_value(history, "start_time", "end_time", default=""),
                    "last_error_message": _first_value(history, "error_message", "message", "data_reason", default=""),
                    "error_count": "1/3" if status == "failed" else "0/3",
                    "duration_seconds": duration,
                    "record_count": record_count,
                }
            task.update(self._runtime_task_snapshots.get(form_name, {}))
            tasks.append(task)
        return tasks

    def _parse_sync_result(self, result: Any) -> dict[str, Any]:
        data = result if isinstance(result, Mapping) else {}
        status = str(_first_value(data, "status", "state", default="success") or "success").strip().lower()
        message = str(_first_value(data, "message", "error", "error_message", default="") or "")
        failed_count = self._to_int(_first_value(data, "failed", "failed_count", default=0))
        audit_status = "failed" if status in {"failed", "failure", "error", "failed_abnormal_exit"} or failed_count > 0 else "success"
        record_count = self._extract_record_count(data)
        duration_seconds = self._to_float(_first_value(data, "duration_seconds", "duration", "elapsed_seconds", default=0))
        return {
            "raw_status": status,
            "audit_status": audit_status,
            "status_label": "成功" if audit_status == "success" else "失败",
            "message": message,
            "record_count": record_count,
            "duration_seconds": duration_seconds,
        }

    def _update_runtime_task_snapshot(
        self,
        task_name: str,
        form_name: str,
        parsed: Mapping[str, Any],
        run_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        audit_status = str(parsed.get("audit_status") or "")
        snapshot = {
            "status": "success" if audit_status == "success" else "failed",
            "last_run": now_text,
            "updated_at": now_text,
            "last_error_time": now_text if audit_status == "failed" else "",
            "last_error_message": parsed.get("message") if audit_status == "failed" else "",
            "error_count": "1/3" if audit_status == "failed" else "0/3",
            "record_count": parsed.get("record_count", 0),
            "duration_seconds": parsed.get("duration_seconds", 0),
            "success_rate": "100%" if audit_status == "success" else "0%",
            "task_name": task_name,
        }
        if run_metadata:
            snapshot.update(dict(run_metadata))
        self._runtime_task_snapshots[form_name] = snapshot

    def _build_run_summary(self, operation: str, task_name: str, parsed: Mapping[str, Any]) -> str:
        status_label = str(parsed.get("status_label") or "--")
        record_count = self._format_count(parsed.get("record_count", 0))
        duration = self._format_duration(parsed.get("duration_seconds", 0))
        return f"{operation}：{task_name}，{status_label}，写入 {record_count} 行，耗时 {duration}"

    def _build_run_detail(self, task_name: str, parsed: Mapping[str, Any]) -> str:
        parts = [
            f"状态 {parsed.get('status_label') or '--'}",
            f"写入 {self._format_count(parsed.get('record_count', 0))} 行",
            f"耗时 {self._format_duration(parsed.get('duration_seconds', 0))}",
        ]
        message = str(parsed.get("message") or "").strip()
        if message:
            parts.append(message)
        return f"{task_name}：{'；'.join(parts)}"

    def _update_progress_task_snapshot(self, task_name: str, progress_stage: str, progress_percent: int) -> None:
        form_name = self._form_name_from_task(task_name)
        if not form_name:
            return
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot = self._runtime_task_snapshots.setdefault(
            form_name,
            {
                "task_name": task_name,
                "status": "running",
                "last_run": now_text,
                "success_rate": "--",
            },
        )
        snapshot.update(
            {
                "task_name": task_name,
                "status": "running",
                "updated_at": now_text,
                "progress_stage": progress_stage,
                "progress_percent": progress_percent,
                "progress_updated_at": now_text,
                "success_rate": "--",
            }
        )

    def _extract_record_count(self, data: Mapping[str, Any]) -> int:
        total = _first_value(data, "total_records", "record_count", "records", "rows", default=None)
        if total not in (None, ""):
            return self._to_int(total)
        inserted = self._to_int(_first_value(data, "inserted", "insert_count", default=0))
        updated = self._to_int(_first_value(data, "updated", "update_count", default=0))
        return inserted + updated

    @staticmethod
    def _to_int(value: Any) -> int:
        if value in (None, ""):
            return 0
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _format_count(cls, value: Any) -> str:
        return f"{cls._to_int(value):,}"

    @classmethod
    def _format_duration(cls, value: Any) -> str:
        seconds = cls._to_float(value)
        if seconds.is_integer():
            return f"{int(seconds)} 秒"
        return f"{seconds:.1f} 秒"

    def _latest_history_by_form(self) -> dict[str, dict[str, Any]]:
        try:
            records, _ = self.history_manager.get_history(page=1, page_size=200)
        except Exception:
            records = []
        result: dict[str, dict[str, Any]] = {}
        for record in records or []:
            if not isinstance(record, Mapping):
                continue
            form_name = str(_first_value(record, "form_name", "task_name", "table_name", default="")).replace("同步", "")
            if form_name and form_name not in result:
                result[form_name] = dict(record)
        return result

    def _set_task_enabled(self, task_name: str, enabled: bool) -> int:
        form_name = self._form_name_from_task(task_name)
        mapping = self._table_mapping()
        if not form_name or form_name not in mapping:
            return 0
        defaults = set(self._sync_config().get("default_forms") or [])
        if enabled:
            defaults.add(form_name)
        else:
            defaults.discard(form_name)
        self._save_default_forms(sorted(defaults))
        return 1

    def _validate_task_before_run(self, task_name: str, form_name: str) -> None:
        reasons: list[str] = []
        sync_config = self._sync_config()
        default_forms = set(sync_config.get("default_forms") or [])
        if default_forms and form_name not in default_forms:
            reasons.append("任务未启用")

        mapping = self._table_mapping()
        if not mapping.get(form_name):
            reasons.append("缺少表单映射")

        if not reasons:
            return

        message = "；".join(reasons)
        detail = f"{task_name}：{message}"
        self._record_operation_audit("运行前校验", "failed", f"运行前校验失败：{task_name}", detail)
        raise ValueError(message)

    def _save_default_forms(self, forms: list[str]) -> None:
        mode = str(self._sync_config().get("sync_type") or "incremental")
        self.config_manager.save_sync_preferences(forms, mode)

    def _form_name_from_task(self, task_name: str) -> str:
        candidate = task_name[:-2] if task_name.endswith("同步") else task_name
        mapping = self._table_mapping()
        if candidate in mapping:
            return candidate
        for task in self._build_tasks():
            if task.get("task_name") == task_name:
                return str(task.get("form_key") or task.get("scope") or "")
        return ""

    def _table_mapping(self) -> dict[str, str]:
        try:
            return dict(self.config_manager.get_table_mapping() or {})
        except Exception:
            return {}

    def _sync_config(self) -> dict[str, Any]:
        try:
            return dict(self.config_manager.get_sync_config() or {})
        except Exception:
            return {}

    def _increment_field(self, form_name: str, table_name: str | None = None) -> str:
        try:
            if table_name:
                field = self.config_manager.get_increment_field(table_name)
                if field:
                    return field
            return self.config_manager.get_increment_field(form_name) or "--"
        except Exception:
            return "--"

    def _target_table_key(self, form_name: str) -> str:
        return self._table_mapping().get(form_name) or form_name

    @staticmethod
    def _sync_mode_label(value: Any) -> str:
        normalized = TaskService._normalize_sync_mode(value)
        if normalized == "complete":
            return "完全同步"
        return "增量同步"

    def _sync_type(self) -> SyncType:
        normalized = self._normalize_sync_mode(self._sync_config().get("sync_type"))
        if normalized == "complete":
            return SyncType.COMPLETE
        return SyncType.INCREMENTAL

    @staticmethod
    def _normalize_sync_mode(value: Any) -> str:
        normalized = str(value or "incremental").strip().lower()
        if normalized in {"full", "complete", "reset"}:
            return "complete"
        if normalized == "incremental":
            return "incremental"
        return "incremental"

    @staticmethod
    def _success_rate(history: Mapping[str, Any]) -> str:
        status = str(history.get("status", "")).lower()
        if status == "success":
            return "100%"
        if status in {"failed", "failure", "error"}:
            return "0%"
        return "--"

    def _filter_tasks(self, tasks: list[dict[str, Any]], filters: Mapping[str, str]) -> list[dict[str, Any]]:
        if not filters:
            return tasks
        status_filter = filters.get("status")
        mode_filter = filters.get("sync_mode")
        keyword = (filters.get("keyword") or "").strip().lower()
        result: list[dict[str, Any]] = []
        for task in tasks:
            if status_filter and _status_text(task.get("status")) != status_filter:
                continue
            if mode_filter and str(task.get("sync_mode") or "") != mode_filter:
                continue
            haystack = " ".join(str(task.get(key) or "") for key in ("task_name", "form_name", "scope", "target_table")).lower()
            if keyword and keyword not in haystack:
                continue
            result.append(task)
        return result


task_service = TaskService()
