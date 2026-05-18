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

    def test_check_connections_logs_session_preflight_success(self) -> None:
        manager = DataSyncManager()

        with (
            patch("src.core.data_sync.kingdee_client") as mock_kingdee_client,
            patch("src.core.data_sync.mysql_manager") as mock_mysql_manager,
            self.assertLogs("src.core.data_sync", level="INFO") as captured,
        ):
            mock_kingdee_client.test_connection.return_value = True
            mock_mysql_manager.test_connection.return_value = True

            connected = manager._check_connections()

        self.assertTrue(connected)
        joined = "\n".join(captured.output)
        self.assertIn("开始同步前连接预检", joined)
        self.assertIn("金蝶会话预检通过", joined)
        self.assertIn("数据库连接预检通过", joined)

class AutoSyncSchedulerSyncTypeTests(unittest.TestCase):
    @patch("src.core.scheduler.config_manager.update_config")
    @patch("src.core.scheduler.schedule.every")
    @patch("src.core.scheduler.schedule.clear")
    def test_configure_sync_forces_incremental_mode(
        self,
        _mock_schedule_clear: Mock,
        mock_schedule_every: Mock,
        mock_update_config: Mock,
    ) -> None:
        mock_schedule_every.return_value.minutes.do.return_value = None
        scheduler = AutoSyncScheduler()

        scheduler.configure_sync(["sales_order"], SyncType.FULL, 30)

        self.assertEqual(scheduler.sync_type, SyncType.INCREMENTAL)
        mock_update_config.assert_any_call("SYNC", "sync_type", SyncType.INCREMENTAL.value)

    def test_execute_sync_always_uses_incremental_mode(self) -> None:
        scheduler = AutoSyncScheduler()
        scheduler.status = SchedulerStatus.RUNNING
        scheduler.sync_forms = ["sales_order"]
        scheduler.sync_type = SyncType.FULL

        with patch("src.core.scheduler.sync_manager") as mock_sync_manager:
            mock_sync_manager.is_shutdown_requested.return_value = False
            mock_sync_manager.sync_data.return_value = {
                "status": "success",
                "details": {},
            }
            scheduler._execute_sync()

        mock_sync_manager.sync_data.assert_called_once_with(
            ["sales_order"],
            SyncType.INCREMENTAL,
        )
        self.assertEqual(scheduler.sync_type, SyncType.INCREMENTAL)


if __name__ == "__main__":
    unittest.main()
