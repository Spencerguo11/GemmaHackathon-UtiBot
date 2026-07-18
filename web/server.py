"""FastAPI web application for Utility Coordinator."""
from __future__ import annotations

import asyncio
import tempfile
import threading
from decimal import Decimal, InvalidOperation
from pathlib import Path
from queue import Empty, Queue
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import PROJECT_ROOT, get_settings
from database import get_session, init_db
from database.repositories import (
    AuditRepository,
    BillRepository,
    JobRepository,
    PaymentTaskRepository,
    TransactionRepository,
)
from models import BillStatus
from services import OllamaClient
from services.agent_steps import AgentStepEmitter
from services.approval_gate import approval_gate, describe_tool_action
from services.chat_history import (
    add_message as save_chat_message,
    create_session as create_chat_session,
    delete_session as delete_chat_session,
    get_session_messages,
    list_sessions as list_chat_sessions,
)
from services.run_registry import run_registry
from agents.coordinator_agent import run_coordinator_chat
from services.data_cleanup import clear_bills, clear_payments, clear_report, clear_workspace
from services.payment_service import prepare_mock_payment, submit_mock_payment
from workflows.ingestion_workflow import process_upload_zip

settings = get_settings()
WEB_DIR = PROJECT_ROOT / "web"
STATIC_DIR = WEB_DIR / "static"

init_db()

app = FastAPI(title="Utility Coordinator AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# run_id -> Queue of SSE events
_event_queues: dict[str, Queue] = {}


class BillUpdate(BaseModel):
    provider_name: str | None = None
    utility_type: str | None = None
    account_number_masked: str | None = None
    service_address: str | None = None
    amount_due: float | None = None
    due_date: str | None = None
    verified_payment_url: str | None = None
    status: str | None = None
    review_reason: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def _bill_dict(bill) -> dict[str, Any]:
    pay_online = bill.document_payment_url or bill.verified_payment_url or ""
    return {
        "bill_id": bill.bill_id,
        "job_id": bill.job_id,
        "provider": bill.provider_name,
        "utility_type": bill.utility_type.value,
        "masked_account": bill.account_number_masked,
        "service_address": bill.service_address,
        "billing_period": f"{bill.billing_period_start} → {bill.billing_period_end}",
        "amount_due": float(bill.amount_due),
        "due_date": bill.due_date,
        "document_payment_url": bill.document_payment_url or "",
        "verified_payment_url": bill.verified_payment_url or "",
        "pay_online_url": pay_online,
        "payment_url": pay_online,
        "confidence": bill.extraction_confidence,
        "status": bill.status.value,
        "review_reason": bill.review_reason or "",
        "requires_review": bill.requires_review,
    }


def _task_dict(task, bill) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "bill_id": task.bill_id,
        "job_id": task.job_id,
        "priority": task.priority,
        "status": task.status.value,
        "provider": bill.provider_name if bill else "",
        "amount_due": float(bill.amount_due) if bill else 0,
        "due_date": bill.due_date if bill else "",
        "failure_reason": task.failure_reason or "",
    }


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    client = OllamaClient()
    return {
        "ollama_available": client.is_available(),
        "model": settings.ollama_model,
        "min_confidence": settings.min_confidence,
        "high_amount_threshold": settings.high_amount_review_threshold,
    }


@app.get("/api/chat/sessions")
def api_list_chat_sessions() -> dict[str, Any]:
    session = get_session()
    try:
        return {"sessions": list_chat_sessions(session)}
    finally:
        session.close()


@app.post("/api/chat/sessions")
def api_create_chat_session() -> dict[str, Any]:
    session = get_session()
    try:
        return {"session": create_chat_session(session)}
    finally:
        session.close()


@app.get("/api/chat/sessions/{session_id}")
def api_get_chat_session(session_id: str) -> dict[str, Any]:
    session = get_session()
    try:
        payload = get_session_messages(session, session_id)
        if not payload:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return payload
    finally:
        session.close()


@app.delete("/api/chat/sessions/{session_id}")
def api_delete_chat_session(session_id: str) -> dict[str, Any]:
    session = get_session()
    try:
        if not delete_chat_session(session, session_id):
            raise HTTPException(status_code=404, detail="Chat session not found")
        return {"success": True}
    finally:
        session.close()


@app.post("/api/chat")
async def chat_with_agent(payload: ChatRequest) -> dict[str, str]:
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    run_id = uuid4().hex
    queue: Queue = Queue()
    _event_queues[run_id] = queue

    db = get_session()
    try:
        chat_session_id = payload.session_id
        if not chat_session_id:
            chat_session_id = create_chat_session(db)["session_id"]
        save_chat_message(db, chat_session_id, "user", message)
    finally:
        db.close()

    def worker() -> None:
        emitter = AgentStepEmitter(callback=queue.put)
        session = get_session()
        try:
            result = run_coordinator_chat(
                message,
                session,
                run_id,
                steps=emitter,
                chat_session_id=chat_session_id,
            )
            if result.get("cancelled") and not result.get("message"):
                result["message"] = "Stopped by user."
            emitter.done({**result, "session_id": chat_session_id})
        except Exception as exc:
            emitter.error("Coordinator failed", str(exc))
            emitter.done({"success": False, "error": str(exc), "session_id": chat_session_id})
        finally:
            session.close()

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id, "session_id": chat_session_id}


@app.post("/api/runs/{run_id}/stop")
def stop_run(run_id: str) -> dict[str, Any]:
    if not run_registry.cancel(run_id):
        raise HTTPException(status_code=404, detail="Run not found or already finished")
    return {"success": True, "stopped": True}


@app.post("/api/runs/{run_id}/approve")
def approve_run_action(run_id: str, payload: ApprovalRequest) -> dict[str, Any]:
    if not approval_gate.resolve(run_id, payload.approved):
        raise HTTPException(status_code=404, detail="No pending approval for this run")
    return {"success": True, "approved": payload.approved}


@app.post("/api/jobs/upload")
async def upload_zip(file: UploadFile = File(...)) -> dict[str, str]:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a ZIP file")

    run_id = uuid4().hex
    queue: Queue = Queue()
    _event_queues[run_id] = queue

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    def worker() -> None:
        emitter = AgentStepEmitter(callback=queue.put)
        run_registry.register(run_id)
        approval_gate.register(run_id)
        session = get_session()
        try:
            description = describe_tool_action("process_zip", {"path": file.filename or str(tmp_path)})
            emitter.permission(
                "Approval required before execution",
                description,
                approval_type="tool_execution",
                run_id=run_id,
                tool="process_zip",
                args={"path": file.filename or str(tmp_path)},
            )
            if not approval_gate.request(
                run_id,
                {"approval_type": "tool_execution", "tool": "process_zip", "description": description},
            ):
                emitter.warning("Denied", "Upload processing cancelled by user")
                emitter.done({"success": False, "message": "Upload cancelled by user."})
                return
            emitter.success("Approved", "User allowed ZIP processing")
            result = process_upload_zip(tmp_path, session, steps=emitter)
            emitter.done(result)
        except Exception as exc:
            emitter.error("Unexpected error", str(exc))
            emitter.done({"success": False, "errors": [str(exc)]})
        finally:
            approval_gate.cleanup(run_id)
            run_registry.cleanup(run_id)
            session.close()
            tmp_path.unlink(missing_ok=True)

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str) -> StreamingResponse:
    queue = _event_queues.get(run_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generator():
        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(None, queue.get, True, 30)
            except Empty:
                yield AgentStepEmitter.to_sse({"type": "ping"})
                continue
            yield AgentStepEmitter.to_sse(event)
            if event.get("type") == "done":
                _event_queues.pop(run_id, None)
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/bills")
def list_bills(job_id: str | None = None) -> dict[str, Any]:
    session = get_session()
    try:
        repo = BillRepository(session)
        bills = repo.get_by_job(job_id) if job_id else repo.list_all()
        return {"bills": [_bill_dict(b) for b in bills]}
    finally:
        session.close()


@app.patch("/api/bills/{bill_id}")
def update_bill(bill_id: str, payload: BillUpdate) -> dict[str, Any]:
    session = get_session()
    try:
        repo = BillRepository(session)
        bill = repo.get(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")

        updates = payload.model_dump(exclude_unset=True)
        if "amount_due" in updates:
            updates["amount_due"] = Decimal(str(updates["amount_due"]))
        if "status" in updates:
            updates["requires_review"] = updates["status"] == BillStatus.NEEDS_REVIEW.value
        repo.update(bill_id, **updates)
        return {"bill": _bill_dict(repo.get(bill_id))}
    finally:
        session.close()


@app.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    session = get_session()
    try:
        task_repo = PaymentTaskRepository(session)
        bill_repo = BillRepository(session)
        tasks = task_repo.list_all()
        result = []
        for task in tasks:
            bill = bill_repo.get(task.bill_id)
            result.append(_task_dict(task, bill))
        return {"tasks": result}
    finally:
        session.close()


@app.post("/api/tasks/{task_id}/prepare")
def prepare_task(task_id: str) -> dict[str, str]:
    run_id = uuid4().hex
    queue: Queue = Queue()
    _event_queues[run_id] = queue

    def worker() -> None:
        emitter = AgentStepEmitter(callback=queue.put)
        run_registry.register(run_id)
        approval_gate.register(run_id)
        session = get_session()
        try:
            emitter.permission(
                "Approval required before payment automation",
                f"Prepare mock payment for task {task_id}",
                approval_type="tool_execution",
                run_id=run_id,
                tool="prepare_mock_payment",
                args={"task_id": task_id},
            )
            if not approval_gate.request(
                run_id,
                {"approval_type": "tool_execution", "tool": "prepare_mock_payment", "task_id": task_id},
            ):
                emitter.warning("Denied", "Payment preparation cancelled")
                emitter.done({"success": False, "cancelled": True})
                return
            approval = prepare_mock_payment(session, task_id, steps=emitter)
            emitter.done({"success": True, "approval": approval})
        except Exception as exc:
            emitter.error("Payment preparation failed", str(exc))
            emitter.done({"success": False, "error": str(exc)})
        finally:
            approval_gate.cleanup(run_id)
            run_registry.cleanup(run_id)
            session.close()

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id}


@app.post("/api/tasks/{task_id}/submit")
def submit_task(task_id: str, payload: ApprovalRequest) -> dict[str, str]:
    run_id = uuid4().hex
    queue: Queue = Queue()
    _event_queues[run_id] = queue

    def worker() -> None:
        emitter = AgentStepEmitter(callback=queue.put)
        run_registry.register(run_id)
        session = get_session()
        try:
            result = submit_mock_payment(session, task_id, approved=payload.approved, steps=emitter)
            emitter.done(result)
        except Exception as exc:
            emitter.error("Payment submission failed", str(exc))
            emitter.done({"success": False, "error": str(exc)})
        finally:
            run_registry.cleanup(run_id)
            session.close()

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/report")
def report() -> dict[str, Any]:
    session = get_session()
    try:
        bill_repo = BillRepository(session)
        txn_repo = TransactionRepository(session)
        audit_repo = AuditRepository(session)

        bills = bill_repo.list_all()
        transactions = txn_repo.list_all()
        events = audit_repo.list_recent(limit=100)

        total_due = sum(float(b.amount_due) for b in bills)
        paid = [b for b in bills if b.status == BillStatus.PAID]
        pending = [b for b in bills if b.status in {BillStatus.READY, BillStatus.AWAITING_APPROVAL}]
        failed = [b for b in bills if b.status == BillStatus.FAILED]
        duplicates = [b for b in bills if b.status == BillStatus.DUPLICATE]

        return {
            "summary": {
                "total_bills": len(bills),
                "total_amount_due": round(total_due, 2),
                "paid": len(paid),
                "pending": len(pending),
                "failed": len(failed),
                "duplicates": len(duplicates),
            },
            "transactions": [
                {
                    "provider": t.provider_name,
                    "amount": float(t.amount),
                    "confirmation_number": t.confirmation_number,
                    "screenshot_path": t.screenshot_path,
                    "status": t.verification_status,
                }
                for t in transactions
            ],
            "events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "actor": e.actor,
                    "job_id": e.job_id,
                    "bill_id": e.bill_id or "",
                    "task_id": e.task_id or "",
                }
                for e in events
            ],
        }
    finally:
        session.close()


@app.delete("/api/clear/workspace")
def api_clear_workspace() -> dict[str, Any]:
    session = get_session()
    try:
        counts = clear_workspace(session)
        return {"success": True, "cleared": counts}
    finally:
        session.close()


@app.delete("/api/clear/bills")
def api_clear_bills() -> dict[str, Any]:
    session = get_session()
    try:
        counts = clear_bills(session)
        return {"success": True, "cleared": counts}
    finally:
        session.close()


@app.delete("/api/clear/payments")
def api_clear_payments() -> dict[str, Any]:
    session = get_session()
    try:
        counts = clear_payments(session)
        return {"success": True, "cleared": counts}
    finally:
        session.close()


@app.delete("/api/clear/report")
def api_clear_report() -> dict[str, Any]:
    session = get_session()
    try:
        counts = clear_report(session)
        return {"success": True, "cleared": counts}
    finally:
        session.close()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
