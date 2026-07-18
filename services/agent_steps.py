"""Agent thinking-step events for the web UI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Optional


StepCallback = Callable[[dict[str, Any]], None]


class AgentStepEmitter:
    """Emit Cursor/Claude-style agent activity steps to a callback or queue."""

    def __init__(self, callback: Optional[StepCallback] = None):
        self.callback = callback
        self.current_turn_id = 0

    def _send(self, event: dict[str, Any]) -> dict[str, Any]:
        if self.callback:
            self.callback(event)
        return event

    def start_turn(self, title: str) -> int:
        self.current_turn_id += 1
        return self._send(
            {
                "type": "turn_start",
                "turn_id": self.current_turn_id,
                "title": title,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )["turn_id"]

    def end_turn(self, status: str = "complete", summary: str = "") -> dict[str, Any]:
        return self._send(
            {
                "type": "turn_end",
                "turn_id": self.current_turn_id,
                "status": status,
                "summary": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def chat(self, role: str, content: str) -> dict[str, Any]:
        return self._send(
            {
                "type": "chat",
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def emit(
        self,
        kind: str,
        title: str,
        detail: str = "",
        *,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        event = {
            "type": "step",
            "turn_id": self.current_turn_id,
            "kind": kind,
            "title": title,
            "detail": detail,
            "meta": meta or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return self._send(event)

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
        return self._send(
            {
                "type": "done",
                "result": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @staticmethod
    def to_sse(event: dict[str, Any]) -> str:
        return f"data: {json.dumps(event)}\n\n"
