from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.incremental_retry_queue import IncrementalRetryQueue


class IncrementalRetryQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        base = Path(self.tmpdir.name)
        self.queue = IncrementalRetryQueue(
            queue_file=base / "retry_queue.jsonl",
            streak_file=base / "retry_streaks.json",
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_enqueue_pop_ack_requeue_roundtrip(self) -> None:
        rows = [{"FID": 1, "FBILLNO": "MO001"}, {"FID": 2, "FBILLNO": "MO002"}]
        queued = self.queue.enqueue_rows("prd_mo_form", "prd_mo", rows, "write_failed")
        self.assertEqual(queued, 2)
        self.assertEqual(self.queue.get_queue_size("prd_mo_form"), 2)

        popped = self.queue.pop_batch("prd_mo_form", 10)
        self.assertEqual(len(popped), 2)
        self.assertEqual(self.queue.get_queue_size("prd_mo_form"), 0)

        self.queue.ack_success(popped[:1])
        requeued = self.queue.requeue_failed(popped[1:])
        self.assertEqual(requeued, 1)
        self.assertEqual(self.queue.get_queue_size("prd_mo_form"), 1)

        popped_again = self.queue.pop_batch("prd_mo_form", 10)
        self.assertEqual(len(popped_again), 1)
        self.assertEqual(popped_again[0].payload["FID"], 2)
        self.assertEqual(popped_again[0].retry_count, 1)

    def test_streak_increase_and_reset(self) -> None:
        self.assertEqual(self.queue.get_streak("prd_mo_form"), 0)
        self.assertEqual(self.queue.increase_streak("prd_mo_form"), 1)
        self.assertEqual(self.queue.increase_streak("prd_mo_form"), 2)
        self.assertEqual(self.queue.get_streak("prd_mo_form"), 2)
        self.queue.reset_streak("prd_mo_form")
        self.assertEqual(self.queue.get_streak("prd_mo_form"), 0)


if __name__ == "__main__":
    unittest.main()
