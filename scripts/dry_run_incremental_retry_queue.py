from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.incremental_retry_queue import IncrementalRetryQueue


def main() -> None:
    queue = IncrementalRetryQueue(
        queue_file=Path("logs/retry_queue.dryrun.jsonl"),
        streak_file=Path("logs/retry_streaks.dryrun.json"),
    )

    rows = [{"FID": 1001, "FBILLNO": "MO1001"}, {"FID": 1002, "FBILLNO": None}]
    queued = queue.enqueue_rows("prd_mo_form", "prd_mo", rows, "dryrun_write_failed")

    popped = queue.pop_batch("prd_mo_form", 10)
    success = [record for record in popped if record.payload.get("FBILLNO")]
    failed = [record for record in popped if not record.payload.get("FBILLNO")]
    queue.ack_success(success)
    queue.requeue_failed(failed)
    streak = queue.increase_streak("prd_mo_form") if failed else 0

    print(f"compensation_enqueued={queued}")
    print(f"compensation_retried={len(popped)} success={len(success)} failed={len(failed)}")
    print(f"compensation_streak={streak}")


if __name__ == "__main__":
    main()
