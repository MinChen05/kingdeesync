from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass(slots=True)
class RetryQueueRecord:
    record_id: str
    form_name: str
    table_name: str
    reason: str
    retry_count: int
    created_at: str
    payload: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryQueueRecord":
        return cls(
            record_id=str(data.get("record_id", "")),
            form_name=str(data.get("form_name", "")),
            table_name=str(data.get("table_name", "")),
            reason=str(data.get("reason", "")),
            retry_count=int(data.get("retry_count", 0) or 0),
            created_at=str(data.get("created_at", "")),
            payload=dict(data.get("payload", {}) or {}),
        )


class IncrementalRetryQueue:
    """File-backed compensation queue for incremental sync failures."""

    def __init__(
        self,
        queue_file: str | Path = Path("logs/retry_queue.jsonl"),
        streak_file: str | Path = Path("logs/retry_streaks.json"),
    ) -> None:
        self.queue_file = Path(queue_file)
        self.streak_file = Path(streak_file)
        self._lock = threading.Lock()
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.streak_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_records_unlocked(self) -> List[RetryQueueRecord]:
        if not self.queue_file.exists():
            return []
        records: List[RetryQueueRecord] = []
        for line in self.queue_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            try:
                records.append(RetryQueueRecord.from_dict(obj))
            except Exception:
                continue
        return records

    def _save_records_unlocked(self, records: Iterable[RetryQueueRecord]) -> None:
        lines = [json.dumps(asdict(record), ensure_ascii=False) for record in records]
        content = "\n".join(lines)
        if content:
            content += "\n"
        self.queue_file.write_text(content, encoding="utf-8")

    def _load_streak_unlocked(self) -> Dict[str, int]:
        if not self.streak_file.exists():
            return {}
        try:
            parsed = json.loads(self.streak_file.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        result: Dict[str, int] = {}
        for key, value in parsed.items():
            try:
                result[str(key)] = int(value)
            except Exception:
                result[str(key)] = 0
        return result

    def _save_streak_unlocked(self, data: Dict[str, int]) -> None:
        self.streak_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def enqueue_rows(self, form_name: str, table_name: str, rows: List[Dict[str, Any]], reason: str) -> int:
        if not rows:
            return 0
        with self._lock:
            records = self._load_records_unlocked()
            now = datetime.now().isoformat(timespec="seconds")
            for row in rows:
                payload = dict(row) if isinstance(row, dict) else {"raw": row}
                records.append(
                    RetryQueueRecord(
                        record_id=uuid.uuid4().hex,
                        form_name=form_name,
                        table_name=table_name,
                        reason=reason,
                        retry_count=0,
                        created_at=now,
                        payload=payload,
                    )
                )
            self._save_records_unlocked(records)
        return len(rows)

    def pop_batch(self, form_name: str, limit: int) -> List[RetryQueueRecord]:
        safe_limit = max(1, int(limit or 0))
        with self._lock:
            all_records = self._load_records_unlocked()
            picked: List[RetryQueueRecord] = []
            remain: List[RetryQueueRecord] = []
            for record in all_records:
                if record.form_name == form_name and len(picked) < safe_limit:
                    picked.append(record)
                else:
                    remain.append(record)
            self._save_records_unlocked(remain)
        return picked

    def ack_success(self, records: List[RetryQueueRecord]) -> None:
        # pop_batch already removed records from persistent queue.
        _ = records
        return None

    def requeue_failed(self, records: List[RetryQueueRecord]) -> int:
        if not records:
            return 0
        with self._lock:
            current = self._load_records_unlocked()
            for record in records:
                record.retry_count = int(record.retry_count or 0) + 1
                current.append(record)
            self._save_records_unlocked(current)
        return len(records)

    def get_queue_size(self, form_name: str | None = None) -> int:
        with self._lock:
            records = self._load_records_unlocked()
        if not form_name:
            return len(records)
        return sum(1 for record in records if record.form_name == form_name)

    def increase_streak(self, form_name: str) -> int:
        with self._lock:
            streaks = self._load_streak_unlocked()
            streaks[form_name] = int(streaks.get(form_name, 0)) + 1
            self._save_streak_unlocked(streaks)
            return streaks[form_name]

    def reset_streak(self, form_name: str) -> None:
        with self._lock:
            streaks = self._load_streak_unlocked()
            streaks[form_name] = 0
            self._save_streak_unlocked(streaks)

    def get_streak(self, form_name: str) -> int:
        with self._lock:
            streaks = self._load_streak_unlocked()
            return int(streaks.get(form_name, 0))
