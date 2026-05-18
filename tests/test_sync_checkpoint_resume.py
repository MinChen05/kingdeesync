from __future__ import annotations

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
                last_written_record_keys=["SO001", "SO002"],
            )

            manager.save_checkpoint(checkpoint)
            loaded = manager.load_checkpoint("销售订单", "saleorder", "incremental")

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.next_start_row, 120)
        self.assertEqual(loaded.last_written_record_keys, ["SO001", "SO002"])


if __name__ == "__main__":
    unittest.main()
