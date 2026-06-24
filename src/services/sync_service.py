"""Service-layer facade for GUI sync operations."""

from __future__ import annotations

import logging
from typing import Callable

from src.config.config_manager import config_manager
from src.core.data_sync import SyncType, sync_manager
from src.core.kingdee_api import kingdee_client
from src.core.mysql_manager import mysql_manager

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int], None]


class SyncService:
    """Expose GUI-safe sync operations without direct core singleton wiring in pages/workers."""

    @staticmethod
    def get_available_forms() -> list[str]:
        return sorted(config_manager.get_table_mapping().keys())

    @staticmethod
    def get_sync_config() -> dict:
        return config_manager.get_sync_config()

    @staticmethod
    def sync_type_to_config_value(sync_type: SyncType) -> str:
        if sync_type in (SyncType.COMPLETE, SyncType.RESET):
            return "complete"
        if sync_type == SyncType.FULL:
            return "complete"
        return "incremental"

    def save_sync_preferences(self, forms: list[str] | None, sync_type: SyncType) -> None:
        mode_str = self.sync_type_to_config_value(sync_type)
        config_manager.save_sync_preferences(forms or [], mode_str)
        config_manager.update_config("SYNC", "sync_type", mode_str)

    def sync_data(
        self,
        forms: list[str] | None,
        sync_type: SyncType,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> dict:
        if progress_callback is not None:
            sync_manager.add_sync_callback(progress_callback)

        try:
            return sync_manager.sync_data(forms, sync_type)
        finally:
            if progress_callback is not None:
                try:
                    sync_manager.remove_sync_callback(progress_callback)
                except Exception as exc:
                    logger.debug("Failed to remove sync callback: %s", exc)

    @staticmethod
    def repair_stale_sync_runs() -> int:
        """Repair leftover running sync tasks from abnormal exit or restart."""
        try:
            sync_cfg = config_manager.get_sync_config()
            return mysql_manager.recover_stale_sync_runs(
                reason="Recovered stale running task during application startup or before a new sync",
                heartbeat_timeout_seconds=sync_cfg.get("run_heartbeat_timeout_secs", 120),
            )
        except Exception as exc:
            logger.warning("Failed to repair stale sync runs: %s", exc)
            return 0

    @staticmethod
    def test_connections() -> tuple[bool, bool, str]:
        api_ok = False
        db_ok = False
        messages: list[str] = []

        try:
            db_ok = mysql_manager.test_connection()
            if not db_ok:
                messages.append("数据库连接失败")
        except Exception as exc:
            messages.append(f"数据库连接失败: {exc}")

        try:
            api_ok = bool(kingdee_client.test_connection())
            if not api_ok:
                messages.append("金蝶 API 登录失败")
        except Exception as exc:
            messages.append(f"金蝶 API 连接异常: {exc}")

        return api_ok, db_ok, "\n".join(messages)


sync_service = SyncService()
