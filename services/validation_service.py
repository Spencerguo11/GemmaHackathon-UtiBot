"""Validation service for bills."""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple
from models import Bill, BillStatus, BillExtraction, UtilityType
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class ValidationError(Exception):
    """Raised when bill validation fails."""
    pass


def validate_bill_extraction(
    extraction: BillExtraction,
    original_text: str,
) -> Tuple[bool, List[str]]:
    """
    Validate extracted bill information.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check required fields
    if not extraction.provider_name or extraction.provider_name.strip() == "":
        errors.append("Provider name is missing")
    
    if extraction.amount_due is None or extraction.amount_due <= 0:
        errors.append(f"Amount due must be greater than zero, got: {extraction.amount_due}")
    
    if not extraction.due_date:
        errors.append("Due date is missing")
    else:
        try:
            due_date = datetime.strptime(extraction.due_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Invalid due date format: {extraction.due_date} (expected YYYY-MM-DD)")
            # Don't continue with date checks if format is wrong
            return False, errors
    
    if not extraction.statement_date:
        errors.append("Statement date is missing")
    else:
        try:
            statement_date = datetime.strptime(extraction.statement_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Invalid statement date format: {extraction.statement_date}")
            return False, errors
    
    # Check date logic
    if extraction.due_date and extraction.statement_date:
        if extraction.due_date < extraction.statement_date:
            errors.append(f"Due date ({extraction.due_date}) precedes statement date ({extraction.statement_date})")
    
    # Validate payment URL if provided
    if extraction.document_payment_url:
        if not extraction.document_payment_url.startswith(("http://", "https://")):
            errors.append(f"Payment URL must use http/https: {extraction.document_payment_url}")
    
    # Check confidence
    if extraction.extraction_confidence < settings.min_confidence:
        errors.append(
            f"Low confidence score: {extraction.extraction_confidence:.2f} "
            f"(below threshold {settings.min_confidence})"
        )
    
    # Check for required evidence
    evidence = extraction.evidence or {}
    for required_field in ["amount_due", "due_date"]:
        if required_field not in evidence or not evidence[required_field]:
            errors.append(f"Missing evidence for {required_field}")
    
    # Check if critical values appear in original text
    if extraction.amount_due and str(extraction.amount_due) not in original_text:
        logger.warning(
            f"Amount due {extraction.amount_due} not found in original text. "
            f"May be rounded or formatted differently."
        )
    
    # Flag high amounts for review
    if extraction.amount_due and extraction.amount_due > settings.high_amount_review_threshold:
        errors.append(
            f"High amount flagged for review: ${extraction.amount_due:.2f} "
            f"(above threshold ${settings.high_amount_review_threshold})"
        )
    
    return len(errors) == 0, errors


def create_bill_from_extraction(
    extraction: BillExtraction,
    job_id: str,
    source_filename: str,
    file_hash: str,
) -> Bill:
    """
    Create Bill model from extraction data.
    
    Args:
        extraction: Extracted bill data
        job_id: Job ID
        source_filename: Original filename
        file_hash: SHA-256 hash of file
    
    Returns:
        Bill model
    """
    now = datetime.utcnow()
    
    # Determine if needs review
    requires_review = False
    review_reason = None
    
    if extraction.extraction_confidence < settings.min_confidence:
        requires_review = True
        review_reason = f"Low confidence: {extraction.extraction_confidence:.2f}"
    
    if extraction.amount_due and extraction.amount_due > settings.high_amount_review_threshold:
        requires_review = True
        review_reason = f"High amount: ${extraction.amount_due:.2f}"
    
    # Determine utility type
    utility_type = UtilityType.OTHER
    if extraction.utility_type:
        try:
            utility_type = UtilityType(extraction.utility_type.lower())
        except ValueError:
            utility_type = UtilityType.OTHER
    
    return Bill(
        bill_id="",  # Will be set by repository
        job_id=job_id,
        source_filename=source_filename,
        file_hash=file_hash,
        provider_name=extraction.provider_name or "UNKNOWN",
        utility_type=utility_type,
        account_number_masked=extraction.account_number_masked or "****",
        service_address=extraction.service_address or "UNKNOWN",
        billing_period_start=extraction.billing_period_start or "1900-01-01",
        billing_period_end=extraction.billing_period_end or "1900-01-01",
        statement_date=extraction.statement_date or "1900-01-01",
        due_date=extraction.due_date or "1900-01-01",
        previous_balance=extraction.previous_balance or Decimal("0.00"),
        current_charges=extraction.current_charges or Decimal("0.00"),
        amount_due=extraction.amount_due or Decimal("0.00"),
        document_payment_url=extraction.document_payment_url,
        extraction_confidence=extraction.extraction_confidence,
        status=BillStatus.NEEDS_REVIEW if requires_review else BillStatus.EXTRACTED,
        requires_review=requires_review,
        review_reason=review_reason,
        created_at=now,
        updated_at=now,
    )
