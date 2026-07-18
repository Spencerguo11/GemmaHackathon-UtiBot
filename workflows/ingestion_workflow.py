"""Ingestion workflow."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from config import JOBS_DIR, get_settings
from database.repositories import AuditRepository, BillRepository, JobRepository, PaymentTaskRepository
from ingestion import (
    clean_bill_text,
    detect_logical_duplicates,
    extract_pdf_text,
    extract_pdfs_from_zip,
)
from models import AuditEvent, BillStatus, EventType
from services import OllamaClient, extract_bill_from_text, validate_bill_extraction
from services.agent_steps import AgentStepEmitter
from services.gemma_client import OllamaClientError
from services.task_planner import create_payment_task, is_payment_eligible
from services.validation_service import create_bill_from_extraction, create_review_bill

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
    steps: Optional[AgentStepEmitter] = None,
) -> tuple[bool, str, list[str]]:
    """Process a single PDF bill file."""
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)
    file_hash = hash_file(pdf_path)

    steps = steps or AgentStepEmitter()
    steps.tool("Reading PDF", pdf_path.name, filename=pdf_path.name)

    existing = bill_repo.get_by_hash(file_hash)
    if existing:
        steps.warning("Exact duplicate skipped", pdf_path.name, bill_id=existing.bill_id)
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
        steps.error("PDF extraction failed", str(exc), filename=pdf_path.name)
        return False, "", [f"Corrupt PDF: {exc}"]

    if not text:
        review_reason = "No embedded text found; scanned PDF support is not enabled"
        steps.warning("No embedded text", review_reason, filename=pdf_path.name)
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
    steps.thinking(
        "Analyzing bill with local Gemma",
        f"Extracting structured fields from {pdf_path.name}",
        filename=pdf_path.name,
    )
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

    if is_valid and not bill.requires_review:
        steps.success(
            "Bill validated",
            f"{extraction.provider_name or 'Unknown'} · ${bill.amount_due} due {bill.due_date}",
            bill_id=bill_id,
            confidence=extraction.extraction_confidence,
        )
    else:
        reason = "; ".join(validation_errors) if validation_errors else (bill.review_reason or "Review required")
        steps.warning("Bill flagged for review", reason, bill_id=bill_id)

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
    steps: Optional[AgentStepEmitter] = None,
) -> dict:
    """Process entire ZIP upload."""
    ollama_client = ollama_client or OllamaClient()
    steps = steps or AgentStepEmitter()
    job_repo = JobRepository(session)
    audit_repo = AuditRepository(session)
    task_repo = PaymentTaskRepository(session)

    steps.thinking("Initializing agent", "Checking local Ollama and Gemma model availability")
    try:
        ollama_client.ensure_available()
        steps.success("Ollama ready", f"Model: {ollama_client.model}")
    except OllamaClientError as exc:
        steps.error("Ollama unavailable", str(exc))
        return {
            "job_id": "",
            "success": False,
            "errors": [str(exc)],
            "bills_created": 0,
            "bills_needing_review": 0,
            "duplicates_detected": 0,
        }

    job_id = job_repo.create()
    steps.tool("Job created", f"Assigned job ID {job_id}", job_id=job_id)
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
        steps.tool("Validating ZIP archive", zip_path.name)
        output_dir = JOBS_DIR / job_id
        pdf_paths, extract_errors = extract_pdfs_from_zip(
            zip_path,
            output_dir,
            max_files=settings.max_zip_files,
            max_uncompressed_mb=settings.max_uncompressed_mb,
        )

        if extract_errors:
            for err in extract_errors:
                steps.error("ZIP validation failed", err)
            job_repo.update_status(job_id, "failed", "; ".join(extract_errors))
            return {
                "job_id": job_id,
                "success": False,
                "errors": extract_errors,
                "bills_created": 0,
                "bills_needing_review": 0,
                "duplicates_detected": 0,
            }

        steps.success("ZIP validated", f"Found {len(pdf_paths)} PDF bill(s)")
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

        for index, pdf_path in enumerate(pdf_paths, start=1):
            steps.thinking(
                f"Processing bill {index}/{len(pdf_paths)}",
                pdf_path.name,
                filename=pdf_path.name,
            )
            success, bill_id, validation_errors = process_bill_file(
                pdf_path,
                job_id,
                session,
                ollama_client,
                steps=steps,
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

        steps.thinking("Checking for logical duplicates", "Comparing provider, account, period, amount")
        logical_dups = detect_logical_duplicates(all_bills)
        duplicates_detected = len(logical_dups)
        for bill_id_1, bill_id_2 in logical_dups:
            bill_repo.update(bill_id_1, status=BillStatus.DUPLICATE.value, requires_review=True)
            steps.warning("Logical duplicate detected", f"{bill_id_1} matches {bill_id_2}")
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

        steps.thinking("Building payment queue", "Prioritizing bills by due date")
        tasks_created = 0
        for bill in all_bills:
            refreshed = bill_repo.get(bill.bill_id)
            if refreshed and is_payment_eligible(refreshed):
                task = create_payment_task(refreshed)
                task_id = task_repo.create(task)
                tasks_created += 1
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
        steps.success(
            "Ingestion complete",
            f"{bills_created} bills · {tasks_created} payment tasks · {duplicates_detected} duplicates",
            job_id=job_id,
        )
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
        steps.error("Processing failed", str(exc))
        job_repo.update_status(job_id, "failed", str(exc))
        return {
            "job_id": job_id,
            "success": False,
            "errors": [str(exc)],
            "bills_created": 0,
            "bills_needing_review": 0,
            "duplicates_detected": 0,
        }
