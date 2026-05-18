"""Tests for scheduler gap detection (direction C).

Tests the interval check logic without importing the full scheduler module.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta


def _detect_gap(
    previous_exec_time: datetime | None,
    now: datetime,
    interval_seconds: int,
) -> tuple[bool, float]:
    """Replicates the gap detection logic from scheduler.py _execute_sync."""
    if previous_exec_time is None:
        return False, 0.0
    gap_minutes = (now - previous_exec_time).total_seconds() / 60.0
    interval_minutes = interval_seconds / 60.0
    if interval_minutes > 0 and gap_minutes > interval_minutes * 1.8:
        return True, gap_minutes
    return False, gap_minutes


class GapDetectionTests(unittest.TestCase):
    """验证同步间隔检测逻辑"""

    def setUp(self):
        self.now = datetime(2026, 5, 18, 10, 0, 0)
        self.default_interval = 3600  # 1 小时

    def test_no_previous_exec_no_detection(self):
        """第一次运行（无历史记录）不应触发告警"""
        alarmed, _ = _detect_gap(None, self.now, self.default_interval)
        self.assertFalse(alarmed)

    def test_normal_interval_no_alarm(self):
        """正常间隔（30 分钟 < 阈值 108 分钟）不应触发"""
        prev = self.now - timedelta(minutes=30)
        alarmed, _ = _detect_gap(prev, self.now, self.default_interval)
        self.assertFalse(alarmed)

    def test_gap_exceeds_threshold_triggers_alarm(self):
        """超过 80% 的间隔（2小时 > 1.8小时）应触发告警"""
        prev = self.now - timedelta(minutes=120)
        alarmed, gap = _detect_gap(prev, self.now, self.default_interval)
        self.assertTrue(alarmed)
        self.assertAlmostEqual(gap, 120.0)

    def test_gap_just_below_threshold_no_alarm(self):
        """略低于阈值的间隔不应触发"""
        # 阈值 = 1.8 * 60 = 108 分钟
        prev = self.now - timedelta(minutes=107)
        alarmed, _ = _detect_gap(prev, self.now, self.default_interval)
        self.assertFalse(alarmed)

    def test_gap_exactly_at_threshold_does_not_trigger(self):
        """恰好等于阈值的间隔不应触发（> 不是 >=）"""
        # 1.8 * 60 = 108 分钟
        prev = self.now - timedelta(minutes=108)
        alarmed, _ = _detect_gap(prev, self.now, self.default_interval)
        self.assertFalse(alarmed)

    def test_30_minute_interval_with_gap(self):
        """间隔设置为 30 分钟（1800s），60 分钟间隔应触发"""
        prev = self.now - timedelta(minutes=60)
        alarmed, gap = _detect_gap(prev, self.now, 1800)
        self.assertTrue(alarmed)
        self.assertAlmostEqual(gap, 60.0)

    def test_zero_interval_no_alarm(self):
        """interval_seconds=0 不应触发告警（除零保护）"""
        prev = self.now - timedelta(hours=24)
        alarmed, _ = _detect_gap(prev, self.now, 0)
        self.assertFalse(alarmed)


if __name__ == "__main__":
    unittest.main()
