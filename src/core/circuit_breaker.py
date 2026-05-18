from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class CircuitState:
    consecutive_failures: int = 0
    opened_until: float = 0.0
    last_failure_category: str = ""


class LocalCircuitBreaker:
    """Per-form in-memory circuit breaker for sync scheduling."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        threshold: int = 3,
        cooldown_seconds: int = 30,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self.enabled = enabled
        self.threshold = max(1, int(threshold or 1))
        self.cooldown_seconds = max(0, int(cooldown_seconds or 0))
        self._time_func = time_func or time.monotonic
        self._states: dict[str, CircuitState] = {}
        self._lock = threading.Lock()

    def allow(self, form_name: str) -> bool:
        if not self.enabled:
            return True

        with self._lock:
            state = self._states.get(form_name)
            if state is None:
                return True

            now = self._time_func()
            if state.opened_until > now:
                return False

            if state.opened_until:
                self._states.pop(form_name, None)
            return True

    def record_failure(self, form_name: str, category: str) -> None:
        if not self.enabled:
            return

        with self._lock:
            state = self._states.setdefault(form_name, CircuitState())
            now = self._time_func()
            if state.opened_until and state.opened_until <= now:
                state.consecutive_failures = 0
                state.opened_until = 0.0

            state.consecutive_failures += 1
            state.last_failure_category = str(category or "")
            if state.consecutive_failures >= self.threshold:
                state.opened_until = now + self.cooldown_seconds

    def record_success(self, form_name: str) -> None:
        if not self.enabled:
            return

        with self._lock:
            self._states.pop(form_name, None)
