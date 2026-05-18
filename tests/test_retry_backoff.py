"""Tests for retry backoff delay calculation (direction D).

Tests the formula delay = min(1.0 * (2 ** (retry_count - 1)), 60.0)
used in form_sync_runner.py.
"""

from __future__ import annotations

import unittest


def _compute_delay(retry_count: int) -> float:
    """Replicates the exponential backoff logic."""
    return min(1.0 * (2 ** (retry_count - 1)), 60.0)


class RetryBackoffTests(unittest.TestCase):
    """验证重试指数退避计算"""

    def test_first_retry_is_1_second(self):
        """第 1 次重试 = 1s"""
        self.assertEqual(_compute_delay(1), 1.0)

    def test_second_retry_is_2_seconds(self):
        """第 2 次重试 = 2s"""
        self.assertEqual(_compute_delay(2), 2.0)

    def test_third_retry_is_4_seconds(self):
        """第 3 次重试 = 4s"""
        self.assertEqual(_compute_delay(3), 4.0)

    def test_fourth_retry_is_8_seconds(self):
        """第 4 次重试 = 8s"""
        self.assertEqual(_compute_delay(4), 8.0)

    def test_fifth_retry_is_16_seconds(self):
        """第 5 次重试 = 16s"""
        self.assertEqual(_compute_delay(5), 16.0)

    def test_sixth_retry_is_32_seconds(self):
        """第 6 次重试 = 32s"""
        self.assertEqual(_compute_delay(6), 32.0)

    def test_seventh_retry_is_capped_at_60(self):
        """第 7+ 次重试上限 60s"""
        self.assertEqual(_compute_delay(7), 60.0)

    def test_eighth_retry_also_60(self):
        """第 8 次重试仍然 60s"""
        self.assertEqual(_compute_delay(8), 60.0)

    def test_retry_100_is_60(self):
        """第 100 次重试仍然 60s"""
        self.assertEqual(_compute_delay(100), 60.0)


if __name__ == "__main__":
    unittest.main()
