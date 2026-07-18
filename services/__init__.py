"""Services package."""
from .gemma_client import OllamaClient
from .document_agent import extract_bill_from_images, extract_bill_from_text
from .validation_service import validate_bill_extraction, create_bill_from_extraction, ValidationError

__all__ = [
    "OllamaClient",
    "extract_bill_from_text",
    "extract_bill_from_images",
    "validate_bill_extraction",
    "create_bill_from_extraction",
    "ValidationError",
]
