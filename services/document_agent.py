"""Document extraction agent using Gemma."""
import json
import logging
from decimal import Decimal
from models import BillExtraction
from services.gemma_client import OllamaClient

logger = logging.getLogger(__name__)

# Extraction prompt template
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


def extract_bill_from_text(
    bill_text: str,
    ollama_client: OllamaClient,
) -> BillExtraction:
    """
    Extract structured bill information using Gemma.
    
    Args:
        bill_text: Extracted PDF text
        ollama_client: Configured Ollama client
    
    Returns:
        BillExtraction model
    """
    if not ollama_client.is_available():
        logger.error("Ollama not available")
        return BillExtraction(extraction_confidence=0.0)
    
    # Prepare prompt
    prompt = EXTRACTION_PROMPT.format(text=bill_text[:4000])  # Limit text size
    
    # Get JSON response
    result = ollama_client.extract_json(prompt, temperature=0.0, timeout=120, max_retries=1)
    
    if not result:
        logger.warning("Failed to extract JSON from model")
        return BillExtraction(extraction_confidence=0.0)
    
    # Create extraction object with safety conversion
    try:
        extraction = BillExtraction(
            provider_name=result.get("provider_name"),
            utility_type=result.get("utility_type"),
            account_number_masked=result.get("account_number_masked"),
            service_address=result.get("service_address"),
            billing_period_start=result.get("billing_period_start"),
            billing_period_end=result.get("billing_period_end"),
            statement_date=result.get("statement_date"),
            due_date=result.get("due_date"),
            previous_balance=Decimal(str(result.get("previous_balance", 0))) if result.get("previous_balance") else None,
            current_charges=Decimal(str(result.get("current_charges", 0))) if result.get("current_charges") else None,
            amount_due=Decimal(str(result.get("amount_due", 0))) if result.get("amount_due") else None,
            document_payment_url=result.get("document_payment_url"),
            extraction_confidence=float(result.get("extraction_confidence", 0.0)),
            evidence=result.get("evidence", {}),
        )
        return extraction
    
    except Exception as e:
        logger.error(f"Error creating BillExtraction: {e}")
        logger.debug(f"Result: {result}")
        return BillExtraction(extraction_confidence=0.0)
