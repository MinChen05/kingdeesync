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
