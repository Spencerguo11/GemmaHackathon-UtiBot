"""Test payment priority scoring."""
from datetime import date, datetime
from decimal import Decimal

from models import Bill, BillStatus, UtilityType
from services.task_planner import calculate_priority_score, sort_bills_for_payment


def _bill(due_date: str) -> Bill:
    return Bill(
        bill_id="bill_test",
        job_id="job_test",
        source_filename="a.pdf",
        file_hash="hash",
        provider_name="Rocky Mountain Power Demo",
        utility_type=UtilityType.ELECTRICITY,
        account_number_masked="****1234",
        service_address="123 Main",
        billing_period_start="2026-06-01",
        billing_period_end="2026-06-30",
        statement_date="2026-07-01",
        due_date=due_date,
        current_charges=Decimal("50.00"),
        amount_due=Decimal("50.00"),
        extraction_confidence=0.95,
        status=BillStatus.READY,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_overdue_bill_has_highest_priority():
    today = date(2026, 7, 20)
    overdue = calculate_priority_score(_bill("2026-07-01"), today)
    soon = calculate_priority_score(_bill("2026-07-22"), today)
    later = calculate_priority_score(_bill("2026-08-20"), today)
    assert overdue < soon < later


def test_sort_bills_for_payment():
    today = date(2026, 7, 20)
    bills = [_bill("2026-08-01"), _bill("2026-07-01"), _bill("2026-07-22")]
    sorted_bills = sort_bills_for_payment(bills, today)
    assert sorted_bills[0].due_date == "2026-07-01"
