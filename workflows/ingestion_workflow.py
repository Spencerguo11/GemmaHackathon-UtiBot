"""Ingestion workflow."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config import JOBS_DIR, get_settings
from ingestion import (
    clean_bill_text,
    detect_logical_duplicates,
    extract_pdf_text,
    extract_pdfs_from_zip,
)
from models import AuditEvent, BillStatus, EventType
from services import OllamaClient, extract_bill_from_text, validate_bill_extraction
from services.gemma_client import OllamaClientError
from services.task_planner import create_payment_task, is_payment_eligible
from services.validation_service import create_bill_from_extraction, create_review_bill
from database.repositories import AuditRepository, BillRepository, JobRepository, PaymentTaskRepository

logger = logging.getLogger(__name__)
settings = get_settings()


def hash_file(path: Path) -> str:
    """Calculate SHA-256 hash of file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as handle:
        for byte_block in iter(lambda: handle.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def process_bill_file(
    pdf_path: Path,
    job_id: str,
    session: Session,
    ollama_client: OllamaClient,
) -> tuple[bool, str, list[str]]:
    """Process a single PDF bill file."""
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)
    file_hash = hash_file(pdf_path)

    existing = bill_repo.get_by_hash(file_hash)
    if existing:
        audit_repo.log_event(
            AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=existing.bill_id,
                event_type=EventType.DUPLICATE_DETECTED,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"filename": pdf_path.name, "hash": file_hash},
            )
        )
        return False, "", ["Exact duplicate of existing bill"]

    try:
        text = extract_pdf_text(pdf_path)
    except Exception as exc:
        return False, "", [f"Corrupt PDF: {exc}"]

    if not text:
        review_reason = "No embedded text found; scanned PDF support is not enabled"
        bill = create_review_bill(job_id, pdf_path.name, file_hash, review_reason)
        bill_id = bill_repo.create(bill)
        audit_repo.log_event(
            AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=bill_id,
                event_type=EventType.BILL_FLAGGED_FOR_REVIEW,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"filename": pdf_path.name, "reason": review_reason},
            )
        )
        return True, bill_id, [review_reason]

    cleaned_text = clean_bill_text(text)
    extraction = extract_bill_from_text(cleaned_text, ollama_client)
    is_valid, validation_errors = validate_bill_extraction(extraction, cleaned_text)

    bill = create_bill_from_extraction(
        extraction,
        job_id=job_id,
        source_filename=pdf_path.name,
        file_hash=file_hash,
        validation_errors=validation_errors,
    )
    bill_id = bill_repo.create(bill)

    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=job_id,
            bill_id=bill_id,
            event_type=EventType.PDF_EXTRACTED,
            actor="system",
            timestamp=datetime.utcnow(),
            details_json={"filename": pdf_path.name},
        )
    )
    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=job_id,
            bill_id=bill_id,
            event_type=EventType.BILL_PARSED,
            actor="system",
            timestamp=datetime.utcnow(),
            details_json={
                "filename": pdf_path.name,
                "confidence": extraction.extraction_confidence,
                "provider": extraction.provider_name,
            },
        )
    )

    if is_valid and not bill.requires_review:
        audit_repo.log_event(
            AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=bill_id,
                event_type=EventType.BILL_VALIDATION_PASSED,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={},
            )
        )
    else:
        audit_repo.log_event(
            AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=bill_id,
                event_type=EventType.BILL_FLAGGED_FOR_REVIEW,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"reasons": validation_errors or [bill.review_reason]},
            )
        )

    return True, bill_id, validation_errors


def process_upload_zip(
    zip_path: Path,
    session: Session,
    ollama_client: Optional[OllamaClient] = None,
) -> dict:
    """Process entire ZIP upload."""
    ollama_client = ollama_client or OllamaClient()
    job_repo = JobRepository(session)
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)
    task_repo = PaymentTaskRepository(session)

    try:
        ollama_client.ensure_available()
    except OllamaClientError as exc:
        return {
            "job_id": "",
            "success": False,
            "errors": [str(exc)],
            "bills_created": 0,
            "bills_needing_review": 0,
            "duplicates_detected": 0,
        }

    job_id = job_repo.create()
    audit_repo.log_event(
        AuditEvent(
            event_id="",
            job_id=job_id,
            event_type=EventType.JOB_CREATED,
            actor="user",
            timestamp=datetime.utcnow(),
            details_json={"filename": zip_path.name},
        )
    )

    try:
        output_dir = JOBS_DIR / job_id
        pdf_paths, extract_errors = extract_pdfs_from_zip(
            zip_path,
            output_dir,
            max_files=settings.max_zip_files,
            max_uncompressed_mb=settings.max_uncompressed_mb,
        )

        if extract_errors:
            job_repo.update_status(job_id, "failed", "; ".join(extract_errors))
            return {
                "job_id": job_id,
                "success": False,
                "errors": extract_errors,
                "bills_created": 0,
                "bills_needing_review": 0,
                "duplicates_detected": 0,
            }

        audit_repo.log_event(
            AuditEvent(
                event_id="",
                job_id=job_id,
                event_type=EventType.ZIP_VALIDATED,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"num_pdfs": len(pdf_paths)},
            )
        )

        bills_created = 0
        bills_needing_review = 0
        processing_errors: list[str] = []
        all_bills = []

        for pdf_path in pdf_paths:
            success, bill_id, validation_errors = process_bill_file(
                pdf_path,
                job_id,
                session,
                ollama_client,
            )
            if success and bill_id:
                bills_created += 1
                bill = bill_repo.get(bill_id)
                if bill:
                    all_bills.append(bill)
                    if bill.requires_review or validation_errors:
                        bills_needing_review += 1
            elif not success:
                processing_errors.extend(validation_errors)

        logical_dups = detect_logical_duplicates(all_bills)
        duplicates_detected = len(logical_dups)
        for bill_id_1, bill_id_2 in logical_dups:
            bill_repo.update(bill_id_1, status=BillStatus.DUPLICATE.value, requires_review=True)
            audit_repo.log_event(
                AuditEvent(
                    event_id="",
                    job_id=job_id,
                    bill_id=bill_id_1,
                    event_type=EventType.DUPLICATE_DETECTED,
                    actor="system",
                    timestamp=datetime.utcnow(),
                    details_json={"duplicate_of": bill_id_2},
                )
            )

        for bill in all_bills:
            refreshed = bill_repo.get(bill.bill_id)
            if refreshed and is_payment_eligible(refreshed):
                task = create_payment_task(refreshed)
                task_id = task_repo.create(task)
                audit_repo.log_event(
                    AuditEvent(
                        event_id="",
                        job_id=job_id,
                        bill_id=refreshed.bill_id,
                        task_id=task_id,
                        event_type=EventType.TASK_CREATED,
                        actor="system",
                        timestamp=datetime.utcnow(),
                        details_json={"priority": task.priority},
                    )
                )

        job_repo.update_status(job_id, "completed")
        return {
            "job_id": job_id,
            "success": True,
            "bills_created": bills_created,
            "bills_needing_review": bills_needing_review,
            "duplicates_detected": duplicates_detected,
            "errors": processing_errors,
        }

    except Exception as exc:
        logger.error("Error processing upload: %s", exc, exc_info=True)
        job_repo.update_status(job_id, "failed", str(exc))
        return {
            "job_id": job_id,
            "success": False,
            "errors": [str(exc)],
            "bills_created": 0,
            "bills_needing_review": 0,
            "duplicates_detected": 0,
        }
