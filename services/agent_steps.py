"""Agent thinking-step events for the web UI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional


StepCallback = Callable[[dict[str, Any]], None]


class AgentStepEmitter:
    """Emit Cursor-style agent activity steps to a callback or queue."""

    def __init__(self, callback: Optional[StepCallback] = None):
        self.callback = callback

    def emit(
        self,
        kind: str,
        title: str,
        detail: str = "",
        *,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Emit one agent step. kind: thinking|tool|success|warning|error|permission."""
        event = {
            "type": "step",
            "kind": kind,
            "title": title,
            "detail": detail,
            "meta": meta or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.callback:
            self.callback(event)
        return event

    def thinking(self, title: str, detail: str = "", **meta: Any) -> dict[str, Any]:
        return self.emit("thinking", title, detail, meta=meta)

    def tool(self, title: str, detail: str = "", **meta: Any) -> dict[str, Any]:
        return self.emit("tool", title, detail, meta=meta)

    def success(self, title: str, detail: str = "", **meta: Any) -> dict[str, Any]:
        return self.emit("success", title, detail, meta=meta)

    def warning(self, title: str, detail: str = "", **meta: Any) -> dict[str, Any]:
        return self.emit("warning", title, detail, meta=meta)

    def error(self, title: str, detail: str = "", **meta: Any) -> dict[str, Any]:
        return self.emit("error", title, detail, meta=meta)

    def permission(self, title: str, detail: str = "", **meta: Any) -> dict[str, Any]:
        return self.emit("permission", title, detail, meta=meta)

    def done(self, result: dict[str, Any]) -> dict[str, Any]:
        event = {
            "type": "done",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.callback:
            self.callback(event)
        return event

    @staticmethod
    def to_sse(event: dict[str, Any]) -> str:
        return f"data: {json.dumps(event)}\n\n"
