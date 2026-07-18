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


def _bill_dict(bill) -> dict[str, Any]:
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
        "payment_url": bill.verified_payment_url or "",
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
        session = get_session()
        try:
            result = process_upload_zip(tmp_path, session, steps=emitter)
            emitter.done(result)
        except Exception as exc:
            emitter.error("Unexpected error", str(exc))
            emitter.done({"success": False, "errors": [str(exc)]})
        finally:
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
        session = get_session()
        try:
            approval = prepare_mock_payment(session, task_id, steps=emitter)
            emitter.done({"success": True, "approval": approval})
        except Exception as exc:
            emitter.error("Payment preparation failed", str(exc))
            emitter.done({"success": False, "error": str(exc)})
        finally:
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
        session = get_session()
        try:
            result = submit_mock_payment(session, task_id, approved=payload.approved, steps=emitter)
            emitter.done(result)
        except Exception as exc:
            emitter.error("Payment submission failed", str(exc))
            emitter.done({"success": False, "error": str(exc)})
        finally:
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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
