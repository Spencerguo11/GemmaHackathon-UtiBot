"""Validation service for bills."""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple

from config import get_settings
from models import Bill, BillExtraction, BillStatus, UtilityType
from services.provider_service import get_trusted_payment_url, is_trusted_payment_url
from services.url_extractor import pick_best_payment_url

logger = logging.getLogger(__name__)
settings = get_settings()


class ValidationError(Exception):
    """Raised when bill validation fails."""


def validate_bill_extraction(
    extraction: BillExtraction,
    original_text: str,
) -> Tuple[bool, List[str]]:
    """Validate extracted bill information."""
    errors: list[str] = []

    if not extraction.provider_name or extraction.provider_name.strip() == "":
        errors.append("Provider name is missing")

    if extraction.amount_due is None or extraction.amount_due <= 0:
        errors.append(f"Amount due must be greater than zero, got: {extraction.amount_due}")

    if not extraction.due_date:
        errors.append("Due date is missing")
    else:
        try:
            datetime.strptime(extraction.due_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Invalid due date format: {extraction.due_date} (expected YYYY-MM-DD)")
            return False, errors

    if not extraction.statement_date:
        errors.append("Statement date is missing")
    else:
        try:
            datetime.strptime(extraction.statement_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Invalid statement date format: {extraction.statement_date}")
            return False, errors

    if extraction.due_date and extraction.statement_date:
        if extraction.due_date < extraction.statement_date:
            errors.append(
                f"Due date ({extraction.due_date}) precedes statement date ({extraction.statement_date})"
            )

    if extraction.document_payment_url:
        if not extraction.document_payment_url.startswith(("http://", "https://")):
            errors.append(
                f"Payment URL must use http/https: {extraction.document_payment_url}"
            )
        elif not is_trusted_payment_url(extraction.document_payment_url):
            errors.append(
                "Document payment URL is not in the trusted provider registry"
            )

    if extraction.extraction_confidence < settings.min_confidence:
        errors.append(
            f"Low confidence score: {extraction.extraction_confidence:.2f} "
            f"(below threshold {settings.min_confidence})"
        )

    evidence = extraction.evidence or {}
    for required_field in ["amount_due", "due_date"]:
        if required_field not in evidence or not evidence[required_field]:
            errors.append(f"Missing evidence for {required_field}")

    if extraction.amount_due and str(extraction.amount_due) not in original_text:
        logger.warning(
            "Amount due %s not found verbatim in original text; may be formatted differently.",
            extraction.amount_due,
        )

    if extraction.amount_due and extraction.amount_due > Decimal(str(settings.high_amount_review_threshold)):
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
    validation_errors: list[str] | None = None,
    source_text: str | None = None,
) -> Bill:
    """Create Bill model from extraction data and validation outcome."""
    now = datetime.utcnow()
    validation_errors = validation_errors or []

    requires_review = bool(validation_errors)
    review_reason = "; ".join(validation_errors) if validation_errors else None

    if extraction.extraction_confidence < settings.min_confidence and not requires_review:
        requires_review = True
        review_reason = f"Low confidence: {extraction.extraction_confidence:.2f}"

    utility_type = UtilityType.OTHER
    if extraction.utility_type:
        try:
            utility_type = UtilityType(extraction.utility_type.lower())
        except ValueError:
            utility_type = UtilityType.OTHER

    verified_payment_url = get_trusted_payment_url(extraction.provider_name)
    document_payment_url = pick_best_payment_url(source_text or "", extraction.document_payment_url)
    if not verified_payment_url:
        requires_review = True
        review_reason = review_reason or "Provider not found in trusted registry"

    if requires_review:
        status = BillStatus.NEEDS_REVIEW
    elif validation_errors:
        status = BillStatus.NEEDS_REVIEW
    else:
        status = BillStatus.READY

    return Bill(
        bill_id="",
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
        document_payment_url=document_payment_url,
        verified_payment_url=verified_payment_url,
        extraction_confidence=extraction.extraction_confidence,
        status=status,
        requires_review=requires_review,
        review_reason=review_reason,
        created_at=now,
        updated_at=now,
    )


def create_review_bill(
    job_id: str,
    source_filename: str,
    file_hash: str,
    review_reason: str,
) -> Bill:
    """Create a placeholder bill that requires manual review."""
    now = datetime.utcnow()
    return Bill(
        bill_id="",
        job_id=job_id,
        source_filename=source_filename,
        file_hash=file_hash,
        provider_name="UNKNOWN",
        utility_type=UtilityType.OTHER,
        account_number_masked="****",
        service_address="UNKNOWN",
        billing_period_start="1900-01-01",
        billing_period_end="1900-01-01",
        statement_date="1900-01-01",
        due_date="1900-01-01",
        previous_balance=Decimal("0.00"),
        current_charges=Decimal("0.00"),
        amount_due=Decimal("0.00"),
        extraction_confidence=0.0,
        status=BillStatus.NEEDS_REVIEW,
        requires_review=True,
        review_reason=review_reason,
        created_at=now,
        updated_at=now,
    )
