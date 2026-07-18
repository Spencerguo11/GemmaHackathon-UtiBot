"""Deterministic payment task planning and prioritization."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from models import Bill, BillStatus, PaymentTask, TaskStatus


def calculate_priority_score(bill: Bill, today: date | None = None) -> int:
    """
    Calculate priority score for a bill. Lower score = higher priority.

    Priority order:
    1. Overdue bills
    2. Bills due soon (within 7 days)
    3. Bills due later
    """
    today = today or date.today()
    due = datetime.strptime(bill.due_date, "%Y-%m-%d").date()
    days_until_due = (due - today).days

    if days_until_due < 0:
        return 0
    if days_until_due <= 7:
        return 100 + days_until_due
    return 1000 + days_until_due


def is_payment_eligible(bill: Bill) -> bool:
    """Return True if bill can enter the payment queue."""
    excluded = {BillStatus.DUPLICATE, BillStatus.PAID, BillStatus.FAILED}
    return bill.status not in excluded and not bill.requires_review


def create_payment_task(bill: Bill, today: date | None = None) -> PaymentTask:
    """Create a prioritized payment task for a bill."""
    now = datetime.utcnow()
    return PaymentTask(
        task_id="",
        bill_id=bill.bill_id,
        job_id=bill.job_id,
        priority=calculate_priority_score(bill, today),
        status=TaskStatus.READY,
        created_at=now,
        updated_at=now,
    )


def sort_bills_for_payment(bills: Iterable[Bill], today: date | None = None) -> list[Bill]:
    """Sort bills by payment priority."""
    return sorted(bills, key=lambda bill: calculate_priority_score(bill, today))
