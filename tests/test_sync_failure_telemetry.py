from __future__ import annotations

import unittest

from src.core.sync_failure_telemetry import (
    WriteFailureDetail,
    build_record_keys,
    classify_failure,
    summarize_failure_details,
)


class SyncFailureTelemetryTests(unittest.TestCase):
    def test_classify_failure_prefers_truncation_keyword(self) -> None:
        detail = classify_failure(
            form_name="生产订单主表",
            table_name="prd_mo",
            error_type="ProgrammingError",
            message="String or binary data would be truncated",
            failed_rows=[{"FID": 101, "FBILLNO": "MO001"}],
        )

        self.assertEqual(detail.category, "string_truncation")
        self.assertEqual(detail.record_keys, ["FID=101|FBILLNO=MO001"])
        self.assertFalse(detail.retryable)

    def test_build_record_keys_prefers_fid_then_billno(self) -> None:
        keys = build_record_keys(
            [
                {"FID": 101, "FBILLNO": "MO001"},
                {"FID": 102, "FBILLNO": "MO002"},
            ]
        )

        self.assertEqual(keys, ["FID=101|FBILLNO=MO001", "FID=102|FBILLNO=MO002"])

    def test_summarize_failure_details_groups_by_category(self) -> None:
        details = [
            WriteFailureDetail(category="sql_error", error_type="IntegrityError", message="dup", failed_count=2),
            WriteFailureDetail(category="sql_error", error_type="IntegrityError", message="dup", failed_count=1),
            WriteFailureDetail(category="session_error", error_type="ValueError", message="session", failed_count=3),
        ]

        summary = summarize_failure_details(details)

        self.assertEqual(summary["sql_error"], 3)
        self.assertEqual(summary["session_error"], 3)


if __name__ == "__main__":
    unittest.main()
