"""Track active agent runs and support user-initiated cancellation."""
from __future__ import annotations

import threading
from typing import Any

from services.approval_gate import approval_gate


class RunRegistry:
    """Thread-safe registry of in-flight runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}

    def register(self, run_id: str) -> None:
        with self._lock:
            self._runs[run_id] = {"cancelled": False}

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            entry = self._runs.get(run_id)
            if not entry:
                return False
            entry["cancelled"] = True
        approval_gate.resolve(run_id, False)
        return True

    def is_cancelled(self, run_id: str) -> bool:
        with self._lock:
            entry = self._runs.get(run_id)
            return bool(entry and entry.get("cancelled"))

    def cleanup(self, run_id: str) -> None:
        with self._lock:
            self._runs.pop(run_id, None)


run_registry = RunRegistry()
