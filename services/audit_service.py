"""Audit logging helpers."""
from __future__ import annotations

from datetime import datetime

from models import AuditEvent, EventType
from sqlalchemy.orm import Session

from database.repositories import AuditRepository


def log_audit(
    session: Session,
    *,
    job_id: str,
    event_type: EventType,
    actor: str = "system",
    bill_id: str | None = None,
    task_id: str | None = None,
    details: dict | None = None,
) -> str:
    """Log a sanitized audit event."""
    repo = AuditRepository(session)
    return repo.log_event(
        AuditEvent(
            event_id="",
            job_id=job_id,
            bill_id=bill_id,
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            timestamp=datetime.utcnow(),
            details_json=details or {},
        )
    )
