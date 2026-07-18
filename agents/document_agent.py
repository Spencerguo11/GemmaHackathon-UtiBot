"""Document extraction agent using local Gemma through Ollama.

Supports two extraction paths:
- Text-based: for PDFs with an embedded text layer.
- Vision-based: for scanned/photographed bills with no text layer, using
  Gemma's multimodal (vision) capability to read the bill image directly.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from models import BillExtraction
from services.date_utils import resolve_date_field
from services.gemma_client import OllamaClient

logger = logging.getLogger(__name__)

_JSON_SCHEMA = """{{
  "provider_name": "string or null",
  "utility_type": "electricity|gas|water|other|null",
  "account_number_masked": "string or null",
  "service_address": "string or null",
  "billing_period_start": "YYYY-MM-DD or null",
  "billing_period_end": "YYYY-MM-DD or null",
  "statement_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "previous_balance": "number or null",
  "current_charges": "number or null",
  "amount_due": "number or null",
  "document_payment_url": "http/https URL or null",
  "extraction_confidence": 0.0 to 1.0,
  "evidence": {{
    "provider_name": "exact text quote or null",
    "amount_due": "exact text quote or null",
    "due_date": "exact text exactly as printed, e.g. 07/15/2026, or null",
    "statement_date": "exact text as printed, or null",
    "billing_period_start": "exact text as printed, or null",
    "billing_period_end": "exact text as printed, or null"
  }}
}}"""

_FIELD_GUIDANCE = """Field guidance:
- provider_name: the full official utility company/government name (e.g. "Salt Lake City Public Utilities", "Hyrum City"). Prefer a more complete legal name found anywhere in the document (e.g. "Please make check payable to ...") over a short logo caption.
- If multiple utility types appear on one combined bill (e.g. electric + water + sewer), set utility_type to whichever service has the single largest dollar charge line.
- service_address: use the exact text next to a label literally saying "Service Address" if printed anywhere. Never use the utility company's own PO Box / headquarters address as the service address.
- account_number_masked: the account number exactly as printed.
- amount_due: the single dollar amount printed directly next to "Amount Due", "Total Due", or "Account Balance". This is usually the SAME number as current_charges — previous balance is normally already paid off, so do NOT add previous_balance and current_charges together.
- For every date field, put your best YYYY-MM-DD guess in the main field, AND the exact raw printed text (e.g. "07/15/2026") in the matching evidence field. The raw evidence text is used as the source of truth for the date.
- Use null for any field you truly cannot find. Never invent or compute values that are not printed on the bill. Do not invent payment URLs."""

TEXT_EXTRACTION_PROMPT = f"""Extract utility bill information from the following text. Return ONLY a valid JSON object, no explanatory text before or after.

{_FIELD_GUIDANCE}

BILL TEXT:
{{text}}

Return this JSON schema:
{_JSON_SCHEMA}
"""

VISION_EXTRACTION_PROMPT = f"""You are reading a photo/scan of a printed utility bill (possibly multiple page images). Carefully read all text in the image, including small boxed tables, before answering. Return ONLY a valid JSON object, no markdown, no commentary.

{_FIELD_GUIDANCE}

Return this JSON schema:
{_JSON_SCHEMA}
"""


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _build_extraction(result: dict[str, Any]) -> BillExtraction:
    evidence = result.get("evidence") or {}

    due_date = resolve_date_field(result.get("due_date"), evidence.get("due_date"))
    statement_date = resolve_date_field(result.get("statement_date"), evidence.get("statement_date"))
    billing_period_start = resolve_date_field(
        result.get("billing_period_start"), evidence.get("billing_period_start")
    )
    billing_period_end = resolve_date_field(
        result.get("billing_period_end"), evidence.get("billing_period_end")
    )

    if billing_period_start and billing_period_end and billing_period_start > billing_period_end:
        # Clearly inconsistent (e.g. misread year); safer to drop than store nonsense.
        billing_period_start = None
        billing_period_end = None

    return BillExtraction(
        provider_name=result.get("provider_name"),
        utility_type=result.get("utility_type"),
        account_number_masked=result.get("account_number_masked"),
        service_address=result.get("service_address"),
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
        statement_date=statement_date,
        due_date=due_date,
        previous_balance=_to_decimal(result.get("previous_balance")),
        current_charges=_to_decimal(result.get("current_charges")),
        amount_due=_to_decimal(result.get("amount_due")),
        document_payment_url=result.get("document_payment_url"),
        extraction_confidence=float(result.get("extraction_confidence", 0.0)),
        evidence=evidence,
    )


def extract_bill_from_text(bill_text: str, ollama_client: OllamaClient) -> BillExtraction:
    """Extract structured bill information from embedded PDF text using local Gemma."""
    ollama_client.ensure_available()

    prompt = TEXT_EXTRACTION_PROMPT.format(text=bill_text[:4000])
    result = ollama_client.extract_json(prompt, temperature=0.0, timeout=120, max_retries=1)
    if not result:
        logger.warning("Failed to extract JSON from model (text mode)")
        return BillExtraction(extraction_confidence=0.0)

    try:
        return _build_extraction(result)
    except Exception as exc:
        logger.error("Error creating BillExtraction (text mode): %s", exc)
        logger.debug("Result: %s", result)
        return BillExtraction(extraction_confidence=0.0)


def extract_bill_from_images(
    images: list[bytes],
    ollama_client: OllamaClient,
) -> BillExtraction:
    """
    Extract structured bill information directly from page images using Gemma's
    vision capability. Used as a fallback for scanned/photographed bills that
    have no embedded text layer.
    """
    ollama_client.ensure_available()

    if not images:
        return BillExtraction(extraction_confidence=0.0)

    result = ollama_client.extract_json(
        VISION_EXTRACTION_PROMPT,
        temperature=0.0,
        timeout=180,
        max_retries=1,
        images=images,
    )
    if not result:
        logger.warning("Failed to extract JSON from model (vision mode)")
        return BillExtraction(extraction_confidence=0.0)

    try:
        return _build_extraction(result)
    except Exception as exc:
        logger.error("Error creating BillExtraction (vision mode): %s", exc)
        logger.debug("Result: %s", result)
        return BillExtraction(extraction_confidence=0.0)
