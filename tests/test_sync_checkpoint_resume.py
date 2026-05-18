from __future__ import annotations

import json
import tempfile
import unittest

from src.core.retry_manager import CheckpointManager, SyncCheckpoint


class SyncCheckpointResumeTests(unittest.TestCase):
    def test_checkpoint_round_trip_preserves_richer_resume_state(self) -> None:
        with tempfile.TemporaryDirectory() as checkpoint_dir:
            manager = CheckpointManager(checkpoint_dir=checkpoint_dir)
            checkpoint = SyncCheckpoint(
                form_name="销售订单",
                table_name="saleorder",
                sync_type="incremental",
                start_row=100,
                total_fetched=100,
                total_inserted=95,
                filter_string="FModifyDate > '2026-05-18'",
                status="pending",
                next_start_row=120,
                last_written_record_keys=["FID=1|FBILLNO=SO001", "FID=2|FBILLNO=SO002"],
            )

            manager.save_checkpoint(checkpoint)
            loaded = manager.load_checkpoint("销售订单", "saleorder", "incremental")

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.next_start_row, 120)
        self.assertEqual(loaded.last_written_record_keys, ["FID=1|FBILLNO=SO001", "FID=2|FBILLNO=SO002"])

    def test_legacy_checkpoint_without_richer_fields_loads_with_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as checkpoint_dir:
            manager = CheckpointManager(checkpoint_dir=checkpoint_dir)
            checkpoint_path = manager._get_checkpoint_path(
                SyncCheckpoint(
                    form_name="销售订单",
                    table_name="saleorder",
                    sync_type="incremental",
                ).checkpoint_id
            )
            with open(checkpoint_path, "w", encoding="utf-8") as checkpoint_file:
                json.dump(
                    {
                        "form_name": "销售订单",
                        "table_name": "saleorder",
                        "sync_type": "incremental",
                        "start_row": 40,
                        "total_fetched": 40,
                        "total_inserted": 38,
                        "last_page": 1,
                        "filter_string": "FModifyDate > '2026-05-18'",
                        "timestamp": "2026-05-18 10:00:00",
                        "status": "pending",
                    },
                    checkpoint_file,
                    ensure_ascii=False,
                    indent=2,
                )

            loaded = manager.load_checkpoint("销售订单", "saleorder", "incremental")

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.next_start_row, 0)
        self.assertEqual(loaded.last_written_record_keys, [])


if __name__ == "__main__":
    unittest.main()
