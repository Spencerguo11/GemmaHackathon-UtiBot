"""Test validation service."""
import pytest
from datetime import datetime
from decimal import Decimal
from models import BillExtraction
from services import validate_bill_extraction


def test_validate_bill_requires_provider_name():
    """Test that provider name is required."""
    extraction = BillExtraction(
        provider_name=None,
        amount_due=Decimal("100.00"),
        due_date="2026-08-01",
        statement_date="2026-07-01",
        extraction_confidence=0.95,
        evidence={"amount_due": "test", "due_date": "test"},
    )
    
    is_valid, errors = validate_bill_extraction(extraction, "test")
    assert not is_valid
    assert any("provider" in err.lower() for err in errors)


def test_validate_bill_requires_positive_amount():
    """Test that amount due must be positive."""
    extraction = BillExtraction(
        provider_name="Test Utility",
        amount_due=Decimal("0.00"),
        due_date="2026-08-01",
        statement_date="2026-07-01",
        extraction_confidence=0.95,
        evidence={"amount_due": "test", "due_date": "test"},
    )
    
    is_valid, errors = validate_bill_extraction(extraction, "test")
    assert not is_valid
    assert any("greater than zero" in err.lower() for err in errors)


def test_validate_bill_requires_valid_date_format():
    """Test that dates must be YYYY-MM-DD."""
    extraction = BillExtraction(
        provider_name="Test Utility",
        amount_due=Decimal("100.00"),
        due_date="08/01/2026",  # Wrong format
        statement_date="2026-07-01",
        extraction_confidence=0.95,
        evidence={"amount_due": "test", "due_date": "test"},
    )
    
    is_valid, errors = validate_bill_extraction(extraction, "test")
    assert not is_valid
    assert any("date" in err.lower() and "format" in err.lower() for err in errors)


def test_validate_bill_due_date_must_be_after_statement_date():
    """Test that due date must be after statement date."""
    extraction = BillExtraction(
        provider_name="Test Utility",
        amount_due=Decimal("100.00"),
        due_date="2026-06-01",  # Before statement date
        statement_date="2026-07-01",
        extraction_confidence=0.95,
        evidence={"amount_due": "test", "due_date": "test"},
    )
    
    is_valid, errors = validate_bill_extraction(extraction, "test")
    assert not is_valid
    assert any("precedes" in err.lower() for err in errors)


def test_validate_bill_requires_minimum_confidence():
    """Test that confidence must meet threshold."""
    extraction = BillExtraction(
        provider_name="Test Utility",
        amount_due=Decimal("100.00"),
        due_date="2026-08-01",
        statement_date="2026-07-01",
        extraction_confidence=0.70,  # Below 0.85 default
        evidence={"amount_due": "test", "due_date": "test"},
    )
    
    is_valid, errors = validate_bill_extraction(extraction, "test")
    assert not is_valid
    assert any("confidence" in err.lower() for err in errors)


def test_validate_bill_passes_with_valid_data():
    """Test that valid extraction passes validation."""
    extraction = BillExtraction(
        provider_name="Test Utility",
        amount_due=Decimal("100.00"),
        due_date="2026-08-01",
        statement_date="2026-07-01",
        extraction_confidence=0.95,
        evidence={"amount_due": "Amount: $100.00", "due_date": "Due: 08/01/2026"},
    )
    
    is_valid, errors = validate_bill_extraction(extraction, "Amount: $100.00 Due: 08/01/2026")
    assert is_valid
    assert len(errors) == 0
