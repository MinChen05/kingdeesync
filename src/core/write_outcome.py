from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WriteOutcome:
    inserted: int = 0
    invalid: int = 0
    deduped: int = 0
    failed: int = 0

    @classmethod
    def from_insert_count(cls, inserted: int) -> "WriteOutcome":
        return cls(inserted=max(0, int(inserted or 0)))
