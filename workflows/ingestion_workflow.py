"""Ingestion workflow."""
import logging
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

from ingestion import extract_pdfs_from_zip, extract_pdf_text, clean_bill_text
from ingestion import detect_exact_duplicates, detect_logical_duplicates
from services import OllamaClient, extract_bill_from_text, validate_bill_extraction, create_bill_from_extraction
from database.repositories import BillRepository, AuditRepository, JobRepository
from models import AuditEvent, EventType, BillStatus
from config import JOBS_DIR

logger = logging.getLogger(__name__)


def hash_file(path: Path) -> str:
    """Calculate SHA-256 hash of file."""
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def process_bill_file(
    pdf_path: Path,
    job_id: str,
    session: Session,
    ollama_client: OllamaClient,
) -> tuple[bool, str, list[str]]:
    """
    Process a single PDF bill file.
    
    Returns:
        Tuple of (success, bill_id or error, validation_errors)
    """
    errors = []
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)
    
    try:
        # Extract text
        text = extract_pdf_text(pdf_path)
        if not text:
            error_msg = "No embedded text found; scanned PDF support is not enabled"
            logger.warning(f"{pdf_path.name}: {error_msg}")
            return False, "", [error_msg]
        
        # Clean text
        cleaned_text = clean_bill_text(text)
        
        # Extract structured data from Gemma
        extraction = extract_bill_from_text(cleaned_text, ollama_client)
        
        # Validate extraction
        is_valid, validation_errors = validate_bill_extraction(extraction, cleaned_text)
        
        # Calculate file hash
        file_hash = hash_file(pdf_path)
        
        # Check for exact duplicates
        existing = bill_repo.get_by_hash(file_hash)
        if existing:
            logger.info(f"Exact duplicate detected: {pdf_path.name} matches bill {existing.bill_id}")
            audit_repo.log_event(AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=existing.bill_id,
                event_type=EventType.DUPLICATE_DETECTED,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"filename": pdf_path.name, "hash": file_hash},
            ))
            return False, "", ["Exact duplicate of existing bill"]
        
        # Create bill model
        bill = create_bill_from_extraction(
            extraction,
            job_id=job_id,
            source_filename=pdf_path.name,
            file_hash=file_hash,
        )
        
        # Create bill in database
        bill_id = bill_repo.create(bill)
        
        # Log audit event
        audit_repo.log_event(AuditEvent(
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
        ))
        
        if is_valid:
            audit_repo.log_event(AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=bill_id,
                event_type=EventType.BILL_VALIDATION_PASSED,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={},
            ))
        else:
            audit_repo.log_event(AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=bill_id,
                event_type=EventType.BILL_FLAGGED_FOR_REVIEW,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"reasons": validation_errors},
            ))
        
        return True, bill_id, validation_errors
    
    except Exception as e:
        logger.error(f"Error processing {pdf_path.name}: {e}", exc_info=True)
        return False, "", [str(e)]


def process_upload_zip(
    zip_path: Path,
    session: Session,
    ollama_client: Optional[OllamaClient] = None,
) -> dict:
    """
    Process entire ZIP upload.
    
    Returns:
        Result dict with statistics
    """
    if not ollama_client:
        ollama_client = OllamaClient()
    
    job_repo = JobRepository(session)
    bill_repo = BillRepository(session)
    audit_repo = AuditRepository(session)
    
    # Create job
    job_id = job_repo.create()
    
    # Log job creation
    audit_repo.log_event(AuditEvent(
        event_id="",
        job_id=job_id,
        event_type=EventType.JOB_CREATED,
        actor="user",
        timestamp=datetime.utcnow(),
        details_json={"filename": zip_path.name},
    ))
    
    try:
        # Extract PDFs
        output_dir = JOBS_DIR / job_id
        pdf_paths, extract_errors = extract_pdfs_from_zip(
            zip_path,
            output_dir,
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
        
        # Log ZIP validation
        audit_repo.log_event(AuditEvent(
            event_id="",
            job_id=job_id,
            event_type=EventType.ZIP_VALIDATED,
            actor="system",
            timestamp=datetime.utcnow(),
            details_json={"num_pdfs": len(pdf_paths)},
        ))
        
        # Process each PDF
        bills_created = 0
        bills_needing_review = 0
        all_bills = []
        
        for pdf_path in pdf_paths:
            success, bill_id, validation_errors = process_bill_file(
                pdf_path,
                job_id,
                session,
                ollama_client,
            )
            
            if success:
                bills_created += 1
                bill = bill_repo.get(bill_id)
                if bill:
                    all_bills.append(bill)
                    if bill.requires_review or bill.status == BillStatus.NEEDS_REVIEW:
                        bills_needing_review += 1
        
        # Check for logical duplicates
        logical_dups = detect_logical_duplicates(all_bills)
        
        # Mark logical duplicates
        duplicates_detected = len(logical_dups)
        for bill_id_1, bill_id_2 in logical_dups:
            bill_repo.update(bill_id_1, status=BillStatus.DUPLICATE.value)
            audit_repo.log_event(AuditEvent(
                event_id="",
                job_id=job_id,
                bill_id=bill_id_1,
                event_type=EventType.DUPLICATE_DETECTED,
                actor="system",
                timestamp=datetime.utcnow(),
                details_json={"duplicate_of": bill_id_2},
            ))
        
        job_repo.update_status(job_id, "completed")
        
        return {
            "job_id": job_id,
            "success": True,
            "bills_created": bills_created,
            "bills_needing_review": bills_needing_review,
            "duplicates_detected": duplicates_detected,
            "errors": [],
        }
    
    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        job_repo.update_status(job_id, "failed", str(e))
        return {
            "job_id": job_id,
            "success": False,
            "errors": [str(e)],
            "bills_created": 0,
            "bills_needing_review": 0,
            "duplicates_detected": 0,
        }
