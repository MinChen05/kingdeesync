"""
性能监控模块
收集和分析同步过程中的性能指标
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SyncMetrics:
    """单次同步的性能指标"""

    form_name: str
    run_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    records_fetched: int = 0
    records_inserted: int = 0
    records_invalid: int = 0
    records_deduped: int = 0
    records_failed: int = 0
    failure_categories: Dict[str, int] = field(default_factory=dict)
    api_calls: int = 0
    api_latency_total: float = 0.0
    api_latency_max: float = 0.0
    api_latency_min: float = float("inf")
    db_insert_time: float = 0.0
    retry_count: int = 0
    error_count: int = 0
    page_count: int = 0
    memory_peak_mb: float = 0.0

    @property
    def duration(self) -> float:
        if self.end_time > 0 and self.start_time > 0:
            return self.end_time - self.start_time
        return 0.0

    @property
    def qps(self) -> float:
        """每秒处理记录数"""
        if self.duration > 0 and self.records_inserted > 0:
            return self.records_inserted / self.duration
        return 0.0

    @property
    def success_rate(self) -> float:
        """插入成功率"""
        total = self.records_inserted + self.records_failed
        if total > 0:
            return (self.records_inserted / total) * 100
        return 100.0

    @property
    def avg_api_latency(self) -> float:
        """平均API延迟"""
        if self.api_calls > 0:
            return self.api_latency_total / self.api_calls
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "form_name": self.form_name,
            "duration_seconds": round(self.duration, 3),
            "records_fetched": self.records_fetched,
            "records_inserted": self.records_inserted,
            "records_invalid": self.records_invalid,
            "records_deduped": self.records_deduped,
            "records_failed": self.records_failed,
            "failure_categories": dict(self.failure_categories),
            "qps": round(self.qps, 2),
            "success_rate": round(self.success_rate, 2),
            "api_calls": self.api_calls,
            "avg_api_latency_ms": round(self.avg_api_latency * 1000, 2),
            "max_api_latency_ms": round(self.api_latency_max * 1000, 2),
            "db_insert_time_seconds": round(self.db_insert_time, 3),
            "retry_count": self.retry_count,
            "error_count": self.error_count,
            "page_count": self.page_count,
        }


class MetricsCollector:
    """性能指标收集器（线程安全）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_metrics: Dict[tuple[str, str], SyncMetrics] = {}
        self._history: List[SyncMetrics] = []
        self._global_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_records": 0,
            "total_duration": 0.0,
            "total_retries": 0,
        }

    @staticmethod
    def _normalize_run_id(run_id: str | None) -> str:
        return str(run_id or "")

    def _build_key(self, run_id: str | None, form_name: str) -> tuple[str, str]:
        return self._normalize_run_id(run_id), str(form_name)

    def start_sync(self, run_id: str | None, form_name: str) -> SyncMetrics:
        """开始记录同步指标"""
        with self._lock:
            normalized_run_id = self._normalize_run_id(run_id)
            metrics = SyncMetrics(run_id=normalized_run_id, form_name=form_name, start_time=time.perf_counter())
            self._current_metrics[(normalized_run_id, form_name)] = metrics
            return metrics

    def get_metrics(self, run_id: str | None, form_name: str) -> Optional[SyncMetrics]:
        """获取当前同步的指标"""
        with self._lock:
            return self._current_metrics.get(self._build_key(run_id, form_name))

    def end_sync(self, run_id: str | None, form_name: str, success: bool = True) -> Optional[SyncMetrics]:
        """结束记录同步指标"""
        with self._lock:
            metrics = self._current_metrics.pop(self._build_key(run_id, form_name), None)
            if metrics:
                metrics.end_time = time.perf_counter()
                self._history.append(metrics)
                self._global_stats["total_syncs"] += 1
                if success:
                    self._global_stats["successful_syncs"] += 1
                else:
                    self._global_stats["failed_syncs"] += 1
                self._global_stats["total_records"] += metrics.records_inserted
                self._global_stats["total_duration"] += metrics.duration
                self._global_stats["total_retries"] += metrics.retry_count
            return metrics

    def record_api_call(self, run_id: str | None, form_name: str, latency: float):
        """记录API调用"""
        with self._lock:
            metrics = self._current_metrics.get(self._build_key(run_id, form_name))
            if metrics:
                metrics.api_calls += 1
                metrics.api_latency_total += latency
                metrics.api_latency_max = max(metrics.api_latency_max, latency)
                metrics.api_latency_min = min(metrics.api_latency_min, latency)

    def record_page(self, run_id: str | None, form_name: str, records: int, latency: float):
        """记录分页查询"""
        with self._lock:
            metrics = self._current_metrics.get(self._build_key(run_id, form_name))
            if metrics:
                metrics.page_count += 1
                metrics.records_fetched += records
                metrics.api_calls += 1
                metrics.api_latency_total += latency
                metrics.api_latency_max = max(metrics.api_latency_max, latency)

    def record_insert(self, run_id: str | None, form_name: str, inserted: int, failed: int, duration: float):
        """记录插入操作"""
        with self._lock:
            metrics = self._current_metrics.get(self._build_key(run_id, form_name))
            if metrics:
                metrics.records_inserted += inserted
                metrics.records_failed += failed
                metrics.db_insert_time += duration

    def record_write_outcome(self, run_id: str | None, form_name: str, outcome, duration: float) -> None:
        """记录写库结果聚合。"""
        with self._lock:
            metrics = self._current_metrics.get(self._build_key(run_id, form_name))
            if not metrics:
                return

            metrics.records_inserted += int(getattr(outcome, "inserted", 0) or 0)
            metrics.records_invalid += int(getattr(outcome, "invalid", 0) or 0)
            metrics.records_deduped += int(getattr(outcome, "deduped", 0) or 0)
            metrics.records_failed += int(getattr(outcome, "failed", 0) or 0)
            metrics.db_insert_time += float(duration or 0.0)

            for detail in getattr(outcome, "failure_details", []) or []:
                category = getattr(detail, "category", "")
                if not category:
                    continue
                metrics.failure_categories[category] = (
                    metrics.failure_categories.get(category, 0) + int(getattr(detail, "failed_count", 0) or 0)
                )

    def record_retry(self, run_id: str | None, form_name: str):
        """记录重试"""
        with self._lock:
            metrics = self._current_metrics.get(self._build_key(run_id, form_name))
            if metrics:
                metrics.retry_count += 1

    def record_error(self, run_id: str | None, form_name: str):
        """记录错误"""
        with self._lock:
            metrics = self._current_metrics.get(self._build_key(run_id, form_name))
            if metrics:
                metrics.error_count += 1

    def get_global_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        with self._lock:
            stats = self._global_stats.copy()
            if stats["total_syncs"] > 0:
                stats["success_rate"] = round((stats["successful_syncs"] / stats["total_syncs"]) * 100, 2)
                stats["avg_duration"] = round(stats["total_duration"] / stats["total_syncs"], 3)
                stats["avg_qps"] = (
                    round(stats["total_records"] / stats["total_duration"], 2) if stats["total_duration"] > 0 else 0
                )
            else:
                stats["success_rate"] = 0
                stats["avg_duration"] = 0
                stats["avg_qps"] = 0
            return stats

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取历史指标"""
        with self._lock:
            return [m.to_dict() for m in self._history[-limit:]]

    def get_form_stats(self, form_name: str) -> Dict[str, Any]:
        """获取特定表单的统计"""
        with self._lock:
            form_metrics = [m for m in self._history if m.form_name == form_name]
            if not form_metrics:
                return {"form_name": form_name, "sync_count": 0}

            total_records = sum(m.records_inserted for m in form_metrics)
            total_duration = sum(m.duration for m in form_metrics)
            successful = sum(1 for m in form_metrics if m.records_failed == 0)

            return {
                "form_name": form_name,
                "sync_count": len(form_metrics),
                "total_records": total_records,
                "successful_syncs": successful,
                "success_rate": round((successful / len(form_metrics)) * 100, 2),
                "avg_duration": round(total_duration / len(form_metrics), 3),
                "avg_qps": round(total_records / total_duration, 2) if total_duration > 0 else 0,
                "avg_api_latency_ms": round(sum(m.avg_api_latency for m in form_metrics) / len(form_metrics) * 1000, 2),
            }

    def export_run_snapshot(self, run_id: str | None, form_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """导出指定表单最近一次同步的指标快照。"""
        with self._lock:
            normalized_run_id = self._normalize_run_id(run_id)
            requested_forms = {str(form_name) for form_name in form_names}
            snapshots: Dict[str, Dict[str, Any]] = {}

            for metrics in reversed(self._history):
                if (
                    metrics.run_id != normalized_run_id
                    or metrics.form_name not in requested_forms
                    or metrics.form_name in snapshots
                ):
                    continue
                snapshots[metrics.form_name] = metrics.to_dict()
                if len(snapshots) == len(requested_forms):
                    break

            for form_name in requested_forms:
                if form_name in snapshots:
                    continue
                metrics = self._current_metrics.get((normalized_run_id, form_name))
                if metrics is not None:
                    snapshots[form_name] = metrics.to_dict()

            return snapshots

    def reset(self):
        """重置所有指标"""
        with self._lock:
            self._current_metrics.clear()
            self._history.clear()
            self._global_stats = {
                "total_syncs": 0,
                "successful_syncs": 0,
                "failed_syncs": 0,
                "total_records": 0,
                "total_duration": 0.0,
                "total_retries": 0,
            }

    def export_summary(self) -> str:
        """导出摘要报告"""
        stats = self.get_global_stats()
        lines = [
            "=" * 60,
            "性能监控摘要报告",
            "=" * 60,
            f"总同步次数: {stats['total_syncs']}",
            f"成功次数: {stats['successful_syncs']}",
            f"失败次数: {stats['failed_syncs']}",
            f"成功率: {stats['success_rate']}%",
            f"总记录数: {stats['total_records']}",
            f"平均耗时: {stats['avg_duration']}秒",
            f"平均QPS: {stats['avg_qps']}",
            f"总重试次数: {stats['total_retries']}",
            "-" * 60,
            "各表单统计:",
        ]

        forms = set(m.form_name for m in self._history)
        for form in sorted(forms):
            form_stats = self.get_form_stats(form)
            lines.append(
                f"  {form}: {form_stats['sync_count']}次, "
                f"{form_stats['total_records']}条, "
                f"成功率{form_stats['success_rate']}%"
            )

        lines.append("=" * 60)
        return "\n".join(lines)


# 全局指标收集器实例
metrics_collector = MetricsCollector()
