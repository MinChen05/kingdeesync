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
