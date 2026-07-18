"""Human approval gate for agent tool execution."""
from __future__ import annotations

import threading
from typing import Any, Optional


class ApprovalGate:
    """Thread-safe approval gate keyed by run_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._gates: dict[str, dict[str, Any]] = {}

    def register(self, run_id: str) -> None:
        with self._lock:
            self._gates[run_id] = {
                "event": threading.Event(),
                "approved": None,
                "pending": None,
            }

    def request(self, run_id: str, payload: dict[str, Any], timeout: float = 600) -> bool:
        """Block until the user approves or denies. Returns True if approved."""
        with self._lock:
            gate = self._gates.get(run_id)
            if not gate:
                return False
            gate["pending"] = payload
            gate["approved"] = None
            gate["event"].clear()

        if not gate["event"].wait(timeout=timeout):
            return False

        with self._lock:
            return gate.get("approved") is True

    def resolve(self, run_id: str, approved: bool) -> bool:
        with self._lock:
            gate = self._gates.get(run_id)
            if not gate:
                return False
            gate["approved"] = approved
            gate["event"].set()
            return True

    def pending(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            gate = self._gates.get(run_id)
            return gate.get("pending") if gate else None

    def cleanup(self, run_id: str) -> None:
        with self._lock:
            self._gates.pop(run_id, None)


approval_gate = ApprovalGate()


def describe_tool_action(tool: str, args: dict[str, Any]) -> str:
    """Human-readable description of a planned tool call."""
    if tool == "list_folder":
        return f"List folder contents at {args.get('path', '~/Downloads')}"
    if tool == "find_zip":
        return f"Search for ZIP files under {args.get('path', '~/Downloads')}"
    if tool == "process_zip":
        return f"Extract PDFs, run local Gemma parsing, and save bills from {args.get('path', '')}"
    if tool == "prepare_mock_payment":
        return f"Prepare automated mock payment for task {args.get('task_id', '')}"
    return f"Execute {tool} with {args}"
