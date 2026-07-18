"""Test verification agent."""
from datetime import datetime
from decimal import Decimal

from agents.verification_agent import verify_confirmation_page
from models import Bill, BillStatus, UtilityType


def _bill() -> Bill:
    return Bill(
        bill_id="bill_test",
        job_id="job_test",
        source_filename="a.pdf",
        file_hash="hash",
        provider_name="Rocky Mountain Power Demo",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****4921",
        service_address="123 Main",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date="2026-07-25",
        current_charges=Decimal("87.42"),
        amount_due=Decimal("87.42"),
        extraction_confidence=0.97,
        status=BillStatus.READY,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_verify_confirmation_success():
    page_text = """
    Payment successful!
    Provider: Rocky Mountain Power Demo
    Paid amount: $87.42
    Confirmation number: CONF-ABCD1234
    """
    result = verify_confirmation_page(page_text, _bill())
    assert result.success
    assert result.confirmation_number == "CONF-ABCD1234"


def test_verify_confirmation_amount_mismatch():
    page_text = """
    Payment successful!
    Provider: Rocky Mountain Power Demo
    Paid amount: $10.00
    Confirmation number: CONF-ABCD1234
    """
    result = verify_confirmation_page(page_text, _bill())
    assert not result.success
