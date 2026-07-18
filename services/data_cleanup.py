"""Data cleanup helpers for tab-specific clears."""
from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from config import JOBS_DIR, SCREENSHOTS_DIR
from database.orm_models import (
    AuditEventORM,
    BillORM,
    JobORM,
    PaymentTaskORM,
    TransactionORM,
)


def _remove_tree_contents(directory: Path) -> int:
    """Remove all contents of a directory. Returns number of top-level items removed."""
    if not directory.exists():
        return 0
    count = 0
    for item in directory.iterdir():
        if item.name == ".gitkeep":
            continue
        count += 1
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)
    return count


def clear_bills(session: Session) -> dict[str, int]:
    """Remove all bills and dependent payment records."""
    txn_count = session.query(TransactionORM).delete()
    task_count = session.query(PaymentTaskORM).delete()
    audit_count = session.query(AuditEventORM).filter(AuditEventORM.bill_id.isnot(None)).delete()
    bill_count = session.query(BillORM).delete()
    session.commit()
    return {
        "bills": bill_count,
        "tasks": task_count,
        "transactions": txn_count,
        "audit_events": audit_count,
    }


def clear_payments(session: Session) -> dict[str, int]:
    """Remove payment tasks and transactions only."""
    txn_count = session.query(TransactionORM).delete()
    task_count = session.query(PaymentTaskORM).delete()
    audit_count = session.query(AuditEventORM).filter(AuditEventORM.task_id.isnot(None)).delete()
    session.commit()
    return {
        "tasks": task_count,
        "transactions": txn_count,
        "audit_events": audit_count,
    }


def clear_report(session: Session) -> dict[str, int]:
    """Remove audit timeline and transaction report data."""
    txn_count = session.query(TransactionORM).delete()
    audit_count = session.query(AuditEventORM).delete()
    session.commit()
    return {"transactions": txn_count, "audit_events": audit_count}


def clear_workspace(session: Session) -> dict[str, int]:
    """Reset workspace: jobs, bills, queue, report artifacts, and job folders."""
    txn_count = session.query(TransactionORM).delete()
    audit_count = session.query(AuditEventORM).delete()
    task_count = session.query(PaymentTaskORM).delete()
    bill_count = session.query(BillORM).delete()
    job_count = session.query(JobORM).delete()
    session.commit()

    jobs_removed = _remove_tree_contents(JOBS_DIR)
    screenshots_removed = _remove_tree_contents(SCREENSHOTS_DIR)

    return {
        "jobs": job_count,
        "bills": bill_count,
        "tasks": task_count,
        "transactions": txn_count,
        "audit_events": audit_count,
        "job_folders_removed": jobs_removed,
        "screenshots_removed": screenshots_removed,
    }
