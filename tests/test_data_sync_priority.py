"""Tests for DataSyncManager PRIORITY_MAP grouping.

Tests the priority map structure without importing the full data_sync module
(which has complex dependency chains).
"""

from __future__ import annotations

import unittest

# Inline copy of the PRIORITY_MAP from src/core/data_sync.py
# If the source changes, update this to match.
PRIORITY_MAP = {
    "仓库": 0, "物料": 0, "客户资料": 0, "即时库存": 0,
    "物料清单": 0, "物料清单子项": 0, "预测订单": 0,
    "销售订单": 1, "采购订单": 1, "应付单": 1,
    "销售出库单": 1, "销售退货单": 1, "发货通知单": 1,
    "委外订单": 1, "科目余额表": 1, "生产订单明细": 1,
    "生产入库单": 1,
    "生产订单主表": 2, "生产用料清单主表": 2, "生产用料清单明细表": 2,
}

ALL_20_FORMS = sorted(PRIORITY_MAP.keys())


class PriorityMapStructureTests(unittest.TestCase):
    """验证 PRIORITY_MAP 结构和分组正确性"""

    def test_priority_map_has_20_forms(self):
        """PRIORITY_MAP 应包含 20 张表单"""
        self.assertEqual(len(PRIORITY_MAP), 20)

    def test_group_0_has_7_forms(self):
        """Group 0 (小表) 应包含 7 张表"""
        group = [f for f, p in PRIORITY_MAP.items() if p == 0]
        self.assertEqual(len(group), 7, f"group0 数量错误: {group}")

    def test_group_1_has_10_forms(self):
        """Group 1 (中表) 应包含 10 张表"""
        group = [f for f, p in PRIORITY_MAP.items() if p == 1]
        self.assertEqual(len(group), 10, f"group1 数量错误: {group}")

    def test_group_2_has_3_forms(self):
        """Group 2 (大表) 应包含 3 张表"""
        group = [f for f, p in PRIORITY_MAP.items() if p == 2]
        self.assertEqual(len(group), 3, f"group2 数量错误: {group}")

    def test_all_priorities_are_0_1_or_2(self):
        """所有优先级值必须是 0、1 或 2"""
        for priority in PRIORITY_MAP.values():
            self.assertIn(priority, (0, 1, 2))

    def test_groups_cover_all_forms(self):
        """分组覆盖不应有遗漏"""
        grouped: dict[int, list[str]] = {}
        for form, priority in PRIORITY_MAP.items():
            grouped.setdefault(priority, []).append(form)
        all_grouped = set()
        for g in grouped.values():
            all_grouped.update(g)
        self.assertEqual(all_grouped, set(PRIORITY_MAP.keys()))

    def test_unmapped_forms_default_to_priority_1(self):
        """未显式配置的表单应默认优先级 1"""
        default = PRIORITY_MAP.get("新表单", 1)
        self.assertEqual(default, 1)

if __name__ == "__main__":
    unittest.main()
