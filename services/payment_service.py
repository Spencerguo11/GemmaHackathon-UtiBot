"""Payment orchestration service."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from agents.verification_agent import verify_confirmation_page
from browser.playwright_controller import browser_session, screenshot_path
from database.repositories import AuditRepository, BillRepository, PaymentTaskRepository, TransactionRepository
from models import AuditEvent, BillStatus, EventType, TaskStatus, Transaction
from services.provider_service import is_trusted_payment_url

logger = logging.getLogger(__name__)


def _account_digits(masked_account: str) -> str:
    digits = re.sub(r"\D", "", masked_account)
    return digits or "1234567890"


def _run_electric_flow(page, bill, *, submit: bool) -> None:
    payment_url = bill.verified_payment_url
    if not payment_url or not is_trusted_payment_url(payment_url):
        raise ValueError("Bill does not have a trusted mock payment URL")

    page.goto(payment_url, wait_until="domcontentloaded")
    page.fill("#account_number", _account_digits(bill.account_number_masked))
    page.click("#continue")
    page.wait_for_load_state("domcontentloaded")
    page.fill("#payment_amount", f"{bill.amount_due:.2f}")
    page.click("#continue")
    page.wait_for_load_state("domcontentloaded")

    if submit:
        page.click("#submit_payment")
        page.wait_for_load_state("domcontentloaded")


def prepare_mock_payment(session: Session, task_id: str) -> dict:
    """Navigate to review page and pause before final submission."""
    task_repo = PaymentTaskRepository(session)
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)

    task = task_repo.get(task_id)
    if not task:
        raise ValueError("Task not found")
    bill = bill_repo.get(task.bill_id)
    if not bill:
        raise ValueError("Bill not found")

    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=task.job_id,
            bill_id=bill.bill_id,
            task_id=task_id,
            event_type=EventType.BROWSER_FLOW_STARTED,
            actor="browser_automation",
            timestamp=datetime.utcnow(),
            details_json={"provider": bill.provider_name},
        )
    )

    with browser_session(headless=True) as page:
        _run_electric_flow(page, bill, submit=False)
        if "review your payment" not in page.inner_text("body").lower():
            raise RuntimeError("Could not reach payment review page")

    task_repo.update(task_id, status=TaskStatus.AWAITING_APPROVAL.value)
    bill_repo.update(task.bill_id, status=BillStatus.AWAITING_APPROVAL.value)
    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=task.job_id,
            bill_id=bill.bill_id,
            task_id=task_id,
            event_type=EventType.HUMAN_APPROVAL_REQUESTED,
            actor="system",
            timestamp=datetime.utcnow(),
            details_json={
                "provider": bill.provider_name,
                "amount": str(bill.amount_due),
                "account": bill.account_number_masked,
            },
        )
    )
    return {
        "provider": bill.provider_name,
        "account_number_masked": bill.account_number_masked,
        "amount": str(bill.amount_due),
        "payment_method": "Mock checking account ••••1234",
        "scheduled_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def submit_mock_payment(session: Session, task_id: str, approved: bool = False) -> dict:
    """Submit mock payment only after explicit approval."""
    task_repo = PaymentTaskRepository(session)
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)
    txn_repo = TransactionRepository(session)

    task = task_repo.get(task_id)
    if not task:
        raise ValueError("Task not found")
    bill = bill_repo.get(task.bill_id)
    if not bill:
        raise ValueError("Bill not found")

    if not approved:
        task_repo.update(task_id, status=TaskStatus.CANCELLED.value)
        bill_repo.update(task.bill_id, status=BillStatus.READY.value)
        return {"success": False, "cancelled": True}

    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=task.job_id,
            bill_id=bill.bill_id,
            task_id=task_id,
            event_type=EventType.HUMAN_APPROVAL_GRANTED,
            actor="user",
            timestamp=datetime.utcnow(),
            details_json={},
        )
    )

    screenshot_file = screenshot_path(task_id)
    with browser_session(headless=True) as page:
        _run_electric_flow(page, bill, submit=True)
        page.screenshot(path=str(screenshot_file))
        verification = verify_confirmation_page(page.inner_text("body"), bill)

    now = datetime.utcnow()
    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=task.job_id,
            bill_id=bill.bill_id,
            task_id=task_id,
            event_type=EventType.PAYMENT_SUBMITTED,
            actor="browser_automation",
            timestamp=now,
            details_json={},
        )
    )

    if verification.success:
        task_repo.update(
            task_id,
            status=TaskStatus.COMPLETED.value,
            approved_at=now,
            completed_at=now,
        )
        bill_repo.update(task.bill_id, status=BillStatus.PAID.value)
        audit_repo.log_event(
            AuditEvent(
                event_id="",
                job_id=task.job_id,
                bill_id=task.bill_id,
                task_id=task_id,
                event_type=EventType.PAYMENT_VERIFIED,
                actor="system",
                timestamp=now,
                details_json={"confirmation_number": verification.confirmation_number},
            )
        )
        txn_repo.create(
            Transaction(
                transaction_id="",
                task_id=task_id,
                provider_name=verification.provider_name or bill.provider_name,
                amount=verification.confirmed_amount or bill.amount_due,
                confirmation_number=verification.confirmation_number,
                submitted_at=now,
                verified_at=now,
                verification_status="success",
                screenshot_path=str(screenshot_file),
                created_at=now,
                updated_at=now,
            )
        )
        return {
            "success": True,
            "confirmation_number": verification.confirmation_number,
            "screenshot_path": str(screenshot_file),
        }

    task_repo.update(
        task_id,
        status=TaskStatus.FAILED.value,
        failure_reason=verification.failure_reason,
        completed_at=now,
    )
    bill_repo.update(task.bill_id, status=BillStatus.FAILED.value, requires_review=True)
    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=task.job_id,
            bill_id=task.bill_id,
            task_id=task_id,
            event_type=EventType.PAYMENT_FAILED,
            actor="system",
            timestamp=now,
            details_json={"reason": verification.failure_reason},
        )
    )
    return {
        "success": False,
        "error": verification.failure_reason,
        "screenshot_path": str(screenshot_file),
    }
