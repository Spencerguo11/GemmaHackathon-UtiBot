"""Test duplicate detection."""
import pytest
from datetime import datetime
from decimal import Decimal
from models import Bill, BillStatus, UtilityType
from ingestion import detect_exact_duplicates, detect_logical_duplicates


@pytest.fixture
def sample_bills():
    """Create sample bills for testing."""
    now = datetime.utcnow()
    
    bill1 = Bill(
        bill_id="bill_1",
        job_id="job_1",
        source_filename="bill1.pdf",
        file_hash="hash_1",
        provider_name="Electric Co",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****1234",
        service_address="123 Main St",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date="2026-08-01",
        previous_balance=Decimal("0.00"),
        current_charges=Decimal("100.00"),
        amount_due=Decimal("100.00"),
        extraction_confidence=0.95,
        status=BillStatus.EXTRACTED,
        created_at=now,
        updated_at=now,
    )
    
    # Exact duplicate
    bill2 = Bill(
        bill_id="bill_2",
        job_id="job_1",
        source_filename="bill2.pdf",
        file_hash="hash_1",  # Same hash
        provider_name="Electric Co",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****1234",
        service_address="123 Main St",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date="2026-08-01",
        previous_balance=Decimal("0.00"),
        current_charges=Decimal("100.00"),
        amount_due=Decimal("100.00"),
        extraction_confidence=0.95,
        status=BillStatus.EXTRACTED,
        created_at=now,
        updated_at=now,
    )
    
    # Logical duplicate
    bill3 = Bill(
        bill_id="bill_3",
        job_id="job_1",
        source_filename="bill3.pdf",
        file_hash="hash_3",  # Different hash
        provider_name="Electric Co",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****1234",
        service_address="123 Main St",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date="2026-08-01",
        previous_balance=Decimal("0.00"),
        current_charges=Decimal("100.00"),
        amount_due=Decimal("100.00"),
        extraction_confidence=0.90,
        status=BillStatus.EXTRACTED,
        created_at=now,
        updated_at=now,
    )
    
    return [bill1, bill2, bill3]


def test_detect_exact_duplicates(sample_bills):
    """Test exact duplicate detection."""
    duplicates = detect_exact_duplicates(sample_bills)
    
    assert "hash_1" in duplicates
    assert len(duplicates["hash_1"]) == 2
    assert "bill_1" in duplicates["hash_1"]
    assert "bill_2" in duplicates["hash_1"]


def test_detect_logical_duplicates(sample_bills):
    """Test logical duplicate detection."""
    duplicates = detect_logical_duplicates(sample_bills)
    
    # Should find logical duplicates between all three
    assert len(duplicates) == 3  # 3 pairs: (1,2), (1,3), (2,3)


def test_no_duplicates_for_different_amounts():
    """Test that different amounts are not flagged as duplicates."""
    now = datetime.utcnow()
    
    bill1 = Bill(
        bill_id="bill_1",
        job_id="job_1",
        source_filename="bill1.pdf",
        file_hash="hash_1",
        provider_name="Electric Co",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****1234",
        service_address="123 Main St",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date="2026-08-01",
        previous_balance=Decimal("0.00"),
        current_charges=Decimal("100.00"),
        amount_due=Decimal("100.00"),
        extraction_confidence=0.95,
        status=BillStatus.EXTRACTED,
        created_at=now,
        updated_at=now,
    )
    
    bill2 = Bill(
        bill_id="bill_2",
        job_id="job_1",
        source_filename="bill2.pdf",
        file_hash="hash_2",
        provider_name="Electric Co",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****1234",
        service_address="123 Main St",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date="2026-08-01",
        previous_balance=Decimal("0.00"),
        current_charges=Decimal("150.00"),  # Different amount
        amount_due=Decimal("150.00"),
        extraction_confidence=0.95,
        status=BillStatus.EXTRACTED,
        created_at=now,
        updated_at=now,
    )
    
    duplicates = detect_logical_duplicates([bill1, bill2])
    assert len(duplicates) == 0
