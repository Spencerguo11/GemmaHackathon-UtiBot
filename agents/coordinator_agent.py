"""Chat-driven coordinator agent using local Gemma and safe tools."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from services import OllamaClient
from services.agent_steps import AgentStepEmitter
from services.approval_gate import approval_gate, describe_tool_action
from services.chat_history import add_message as save_chat_message
from services.folder_navigator import find_zip_files, list_directory
from services.run_registry import run_registry
from workflows.ingestion_workflow import process_upload_zip

logger = logging.getLogger(__name__)

MAX_AGENT_STEPS = 12
EXECUTABLE_TOOLS = {"list_folder", "find_zip", "process_zip"}

COORDINATOR_PROMPT = """You are Utility Coordinator, a local AI agent that helps users find ZIP files containing utility bill PDFs and process them.

IMPORTANT: The user must approve every tool execution before it runs. Plan actions, but never assume a tool has already executed.

Respond with JSON only using this schema:
{{
  "thought": "brief internal reasoning",
  "tool": "list_folder|find_zip|process_zip|reply|finish",
  "args": {{}},
  "assistant_message": "short user-facing message explaining what you want to do next"
}}

Tools:
- list_folder: args.path — list entries in a folder
- find_zip: args.path — find ZIP files under a folder
- process_zip: args.path — process one ZIP file of utility bills
- reply: args.message — ask the user a clarifying question, then stop
- finish: args.message — task complete, summarize for the user

Rules:
1. Prefer find_zip before process_zip.
2. Use paths like ~/Downloads, ~/Documents, ~/Desktop, or absolute paths the user mentions.
3. If multiple ZIP files are found, pick the most likely utility-bills archive or the newest one.
4. Never invent file paths that were not discovered by tools.
5. After process_zip succeeds, call finish with a summary.

User request:
{user_message}

Tool history (JSON):
{tool_history}

Respond with the next action JSON only.
"""


def _parse_agent_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


def _execute_tool(
    tool: str,
    args: dict[str, Any],
    session: Session,
    steps: AgentStepEmitter,
    ollama_client: OllamaClient,
) -> dict[str, Any]:
    if tool == "list_folder":
        path = args.get("path") or str(Path.home() / "Downloads")
        steps.tool("Listing folder", path)
        result = list_directory(path)
        steps.success("Folder listed", f"{len(result['entries'])} entries")
        return result

    if tool == "find_zip":
        path = args.get("path") or str(Path.home() / "Downloads")
        steps.tool("Searching for ZIP files", path)
        result = find_zip_files(path)
        count = len(result["zip_files"])
        if count:
            steps.success("ZIP files found", "\n".join(result["zip_files"][:5]))
        else:
            steps.warning("No ZIP files found", path)
        return result

    if tool == "process_zip":
        path = args.get("path")
        if not path:
            raise ValueError("process_zip requires args.path")
        zip_path = Path(path)
        if not zip_path.exists():
            raise ValueError(f"ZIP not found: {path}")
        steps.tool("Processing ZIP archive", str(zip_path))
        result = process_upload_zip(zip_path, session, ollama_client=ollama_client, steps=steps)
        if result.get("success"):
            steps.success(
                "ZIP processed",
                f"{result.get('bills_created', 0)} bills extracted",
            )
        else:
            steps.error("Processing failed", "; ".join(result.get("errors", [])))
        return result

    if tool == "reply":
        message = args.get("message") or args.get("assistant_message") or "Need more information."
        steps.thinking("Waiting for user", message)
        return {"reply": message}

    if tool == "finish":
        message = args.get("message") or args.get("assistant_message") or "Done."
        steps.success("Task complete", message)
        return {"finished": True, "message": message}

    raise ValueError(f"Unknown tool: {tool}")


def _check_cancelled(run_id: str, steps: AgentStepEmitter) -> bool:
    if run_registry.is_cancelled(run_id):
        steps.warning("Stopped", "Run cancelled by user")
        return True
    return False


def _request_tool_approval(
    run_id: str,
    tool: str,
    args: dict[str, Any],
    thought: str,
    steps: AgentStepEmitter,
) -> bool:
    description = describe_tool_action(tool, args)
    steps.permission(
        "Approval required before execution",
        description,
        approval_type="tool_execution",
        run_id=run_id,
        tool=tool,
        args=args,
        thought=thought,
    )
    approved = approval_gate.request(
        run_id,
        {"approval_type": "tool_execution", "tool": tool, "args": args, "description": description},
    )
    if approved:
        steps.success("Approved", f"User allowed: {tool}")
    else:
        steps.warning("Denied", f"User blocked: {tool}")
    return approved


def run_coordinator_chat(
    user_message: str,
    session: Session,
    run_id: str,
    steps: Optional[AgentStepEmitter] = None,
    ollama_client: Optional[OllamaClient] = None,
    chat_session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Run the chat coordinator loop until finish or max steps."""
    steps = steps or AgentStepEmitter()
    ollama_client = ollama_client or OllamaClient()
    ollama_client.ensure_available()

    run_registry.register(run_id)
    approval_gate.register(run_id)
    steps.chat("user", user_message)
    tool_history: list[dict[str, Any]] = []
    assistant_messages: list[str] = []

    try:
        for step_num in range(1, MAX_AGENT_STEPS + 1):
            if _check_cancelled(run_id, steps):
                response = {
                    "success": False,
                    "message": "Stopped by user.",
                    "cancelled": True,
                    "tool_history": tool_history,
                }
                if chat_session_id:
                    save_chat_message(session, chat_session_id, "assistant", response["message"], metadata=response)
                return response

            steps.start_turn(f"Step {step_num}: Plan & request approval")
            steps.thinking("Consulting local Gemma", user_message if step_num == 1 else "Reviewing tool results")

            if _check_cancelled(run_id, steps):
                response = {
                    "success": False,
                    "message": "Stopped by user.",
                    "cancelled": True,
                    "tool_history": tool_history,
                }
                if chat_session_id:
                    save_chat_message(session, chat_session_id, "assistant", response["message"], metadata=response)
                return response

            prompt = COORDINATOR_PROMPT.format(
                user_message=user_message,
                tool_history=json.dumps(tool_history[-6:], indent=2),
            )
            raw = ollama_client.generate(prompt, temperature=0.0, json_format=True)
            if not raw:
                steps.error("Model returned empty response", "Could not plan next action")
                steps.end_turn("error", "Model error")
                break

            try:
                action = _parse_agent_json(raw)
            except json.JSONDecodeError as exc:
                steps.error("Invalid JSON from model", str(exc))
                steps.end_turn("error", "Invalid model output")
                break

            thought = action.get("thought") or ""
            tool = (action.get("tool") or "finish").lower()
            args = action.get("args") or {}
            assistant_message = action.get("assistant_message") or ""

            if thought:
                steps.thinking("Reasoning", thought)
            if assistant_message:
                steps.chat("assistant", assistant_message)
                assistant_messages.append(assistant_message)

            if tool in EXECUTABLE_TOOLS:
                if _check_cancelled(run_id, steps):
                    response = {
                        "success": False,
                        "message": "Stopped by user.",
                        "cancelled": True,
                        "tool_history": tool_history,
                    }
                    if chat_session_id:
                        save_chat_message(session, chat_session_id, "assistant", response["message"], metadata=response)
                    return response
                if not _request_tool_approval(run_id, tool, args, thought, steps):
                    tool_history.append({"tool": tool, "args": args, "denied": True})
                    steps.end_turn("cancelled", "User denied action")
                    return {
                        "success": False,
                        "message": "Action cancelled by user.",
                        "tool_history": tool_history,
                    }

            try:
                result = _execute_tool(tool, args, session, steps, ollama_client)
                tool_history.append({"tool": tool, "args": args, "result": result})
            except Exception as exc:
                logger.exception("Tool execution failed")
                steps.error(f"Tool failed: {tool}", str(exc))
                tool_history.append({"tool": tool, "args": args, "error": str(exc)})
                steps.end_turn("error", str(exc))
                continue

            if tool in {"finish", "reply"}:
                steps.end_turn("complete", assistant_message or "Done")
                last_process = next(
                    (entry["result"] for entry in reversed(tool_history) if entry.get("tool") == "process_zip"),
                    None,
                )
                response = {
                    "success": True,
                    "message": assistant_messages[-1] if assistant_messages else "Done.",
                    "tool_history": tool_history,
                }
                if isinstance(last_process, dict):
                    response.update(last_process)
                if chat_session_id:
                    save_chat_message(session, chat_session_id, "assistant", response["message"], metadata=response)
                return response

            steps.end_turn("complete", f"Executed {tool}")

        final_message = assistant_messages[-1] if assistant_messages else "Reached maximum agent steps."
        steps.warning("Stopped", final_message)
        response = {
            "success": False,
            "message": final_message,
            "tool_history": tool_history,
        }
        if chat_session_id:
            save_chat_message(session, chat_session_id, "assistant", final_message, metadata=response)
        return response
    finally:
        approval_gate.cleanup(run_id)
        run_registry.cleanup(run_id)
