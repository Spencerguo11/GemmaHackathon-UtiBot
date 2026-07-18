"""Tests for the human approval gate."""
import threading
import time

from services.approval_gate import ApprovalGate, describe_tool_action


def test_approve_resolves_request():
    gate = ApprovalGate()
    run_id = "run-1"
    gate.register(run_id)
    result = {}

    def worker():
        result["approved"] = gate.request(run_id, {"tool": "list_folder"})

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(0.05)
    assert gate.resolve(run_id, True)
    thread.join(timeout=2)
    assert result["approved"] is True


def test_deny_resolves_request():
    gate = ApprovalGate()
    run_id = "run-2"
    gate.register(run_id)
    result = {}

    def worker():
        result["approved"] = gate.request(run_id, {"tool": "process_zip"})

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(0.05)
    assert gate.resolve(run_id, False)
    thread.join(timeout=2)
    assert result["approved"] is False


def test_resolve_unknown_run_returns_false():
    gate = ApprovalGate()
    assert gate.resolve("missing", True) is False


def test_describe_tool_action():
    assert "Downloads" in describe_tool_action("list_folder", {"path": "~/Downloads"})
    assert "Search" in describe_tool_action("find_zip", {"path": "~/Documents"})
    assert "Gemma" in describe_tool_action("process_zip", {"path": "/tmp/bills.zip"})
    assert "task-123" in describe_tool_action("prepare_mock_payment", {"task_id": "task-123"})
