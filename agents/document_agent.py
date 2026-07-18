"""Document extraction agent using local Gemma through Ollama."""
from __future__ import annotations

import logging
from decimal import Decimal

from models import BillExtraction
from services.gemma_client import OllamaClient

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Extract utility bill information from the following text. Return ONLY a valid JSON object.

Rules:
1. Return JSON only. No explanatory text before or after.
2. For missing values, use null (not empty string or 0).
3. Extract dates in YYYY-MM-DD format.
4. Extract amounts as numbers without currency symbols.
5. Extract the current AMOUNT DUE (what must be paid now).
6. Provide evidence text for critical fields (provider, amount due, due date).
7. Assign a confidence score from 0.0 to 1.0.
8. Do not invent or guess values.
9. Do not invent payment URLs.

BILL TEXT:
{text}

Return this JSON schema:
{{
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
    "provider_name": "relevant quote from text or null",
    "amount_due": "relevant quote from text or null",
    "due_date": "relevant quote from text or null"
  }}
}}
"""


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def extract_bill_from_text(bill_text: str, ollama_client: OllamaClient) -> BillExtraction:
    """Extract structured bill information using local Gemma."""
    ollama_client.ensure_available()

    prompt = EXTRACTION_PROMPT.format(text=bill_text[:4000])
    result = ollama_client.extract_json(prompt, temperature=0.0, timeout=120, max_retries=1)
    if not result:
        logger.warning("Failed to extract JSON from model")
        return BillExtraction(extraction_confidence=0.0)

    try:
        return BillExtraction(
            provider_name=result.get("provider_name"),
            utility_type=result.get("utility_type"),
            account_number_masked=result.get("account_number_masked"),
            service_address=result.get("service_address"),
            billing_period_start=result.get("billing_period_start"),
            billing_period_end=result.get("billing_period_end"),
            statement_date=result.get("statement_date"),
            due_date=result.get("due_date"),
            previous_balance=_to_decimal(result.get("previous_balance")),
            current_charges=_to_decimal(result.get("current_charges")),
            amount_due=_to_decimal(result.get("amount_due")),
            document_payment_url=result.get("document_payment_url"),
            extraction_confidence=float(result.get("extraction_confidence", 0.0)),
            evidence=result.get("evidence") or {},
        )
    except Exception as exc:
        logger.error("Error creating BillExtraction: %s", exc)
        logger.debug("Result: %s", result)
        return BillExtraction(extraction_confidence=0.0)
