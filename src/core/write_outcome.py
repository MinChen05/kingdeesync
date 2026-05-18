from __future__ import annotations

from dataclasses import dataclass, field

from src.core.sync_failure_telemetry import WriteFailureDetail


@dataclass(slots=True)
class WriteOutcome:
    inserted: int = 0
    invalid: int = 0
    deduped: int = 0
    failed: int = 0
    failure_details: list[WriteFailureDetail] = field(default_factory=list)

    @classmethod
    def from_insert_count(cls, inserted: int) -> "WriteOutcome":
        return cls(inserted=max(0, int(inserted or 0)))
