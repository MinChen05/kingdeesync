from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.core.circuit_breaker import LocalCircuitBreaker
from src.core.data_sync import DataSyncManager, SyncType


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

    def test_allows_again_after_cooldown_expires(self) -> None:
        now_ref = [100.0]
        breaker = LocalCircuitBreaker(
            threshold=2,
            cooldown_seconds=30,
            time_func=lambda: now_ref[0],
        )

        breaker.record_failure("销售订单", "sql_error")
        breaker.record_failure("销售订单", "sql_error")
        self.assertFalse(breaker.allow("销售订单"))

        now_ref[0] += 31
        self.assertTrue(breaker.allow("销售订单"))

    def test_data_sync_manager_returns_circuit_open_without_runner_call(self) -> None:
        with patch("src.core.data_sync.config_manager.get_sync_config", return_value={}):
            manager = DataSyncManager()

        manager.form_sync_runner = Mock()
        manager.circuit_breaker.record_failure("销售订单", "sql_error")
        manager.circuit_breaker.record_failure("销售订单", "sql_error")
        manager.circuit_breaker.record_failure("销售订单", "sql_error")

        result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)

        self.assertEqual(result["status"], "circuit_open")
        self.assertEqual(result["error_type"], "circuit_open")
        manager.form_sync_runner.sync_single_form.assert_not_called()

    def test_partial_result_with_multiple_failure_categories_counts_once(self) -> None:
        config = {
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 2,
            "circuit_breaker_cooldown_secs": 30,
        }
        with patch("src.core.data_sync.config_manager.get_sync_config", side_effect=lambda: dict(config)):
            manager = DataSyncManager()
            manager.form_sync_runner = Mock(
                sync_single_form=Mock(
                    side_effect=[
                        {
                            "status": "partial",
                            "failure_categories": {"sql_error": 2, "session_error": 1},
                            "error_type": "WriteFailure",
                        },
                        {
                            "status": "partial",
                            "failure_categories": {"sql_error": 2, "session_error": 1},
                            "error_type": "WriteFailure",
                        },
                    ]
                )
            )
            first_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)
            second_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)
            third_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)

        self.assertEqual(first_result["status"], "partial")
        self.assertEqual(second_result["status"], "partial")
        self.assertEqual(third_result["status"], "circuit_open")
        self.assertEqual(manager.form_sync_runner.sync_single_form.call_count, 2)

    def test_sync_manager_refreshes_breaker_config_without_rebuild(self) -> None:
        config = {
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_cooldown_secs": 30,
        }
        with patch("src.core.data_sync.config_manager.get_sync_config", side_effect=lambda: dict(config)):
            manager = DataSyncManager()

            now_ref = [100.0]
            manager.circuit_breaker._time_func = lambda: now_ref[0]
            manager.form_sync_runner = Mock(
                sync_single_form=Mock(
                    side_effect=[
                        {"status": "failed", "failure_categories": {"sql_error": 1}, "error_type": "WriteFailure"},
                        {"status": "failed", "failure_categories": {"sql_error": 1}, "error_type": "WriteFailure"},
                        {"status": "success"},
                    ]
                )
            )

            first_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)
            self.assertEqual(first_result["status"], "failed")

            config["circuit_breaker_threshold"] = 1
            config["circuit_breaker_cooldown_secs"] = 10
            second_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)
            third_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)

            self.assertEqual(second_result["status"], "failed")
            self.assertEqual(third_result["status"], "circuit_open")

            config["circuit_breaker_enabled"] = False
            fourth_result = manager._sync_single_form("销售订单", SyncType.INCREMENTAL)

        self.assertEqual(fourth_result["status"], "success")
        self.assertEqual(manager.form_sync_runner.sync_single_form.call_count, 3)


if __name__ == "__main__":
    unittest.main()
