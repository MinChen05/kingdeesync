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


if __name__ == "__main__":
    unittest.main()
