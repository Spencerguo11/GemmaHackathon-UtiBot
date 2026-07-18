"""Tests for tab-specific data cleanup."""
from datetime import datetime
from decimal import Decimal

from database import get_session, init_db
from database.orm_models import AuditEventORM, BillORM, JobORM, PaymentTaskORM, TransactionORM
from models import BillStatus, UtilityType
from services.data_cleanup import clear_bills, clear_payments, clear_report, clear_workspace


def _seed(session):
    job = JobORM(job_id="job_test", status="completed", uploaded_at=datetime.utcnow())
    session.add(job)
    bill = BillORM(
        bill_id="bill_test",
        job_id="job_test",
        source_filename="a.pdf",
        file_hash="abc",
        provider_name="Test",
        utility_type="electricity",
        account_number_masked="****1",
        service_address="123 Main",
        billing_period_start="2026-01-01",
        billing_period_end="2026-01-31",
        statement_date="2026-02-01",
        due_date="2026-02-15",
        previous_balance=Decimal("0"),
        current_charges=Decimal("10"),
        amount_due=Decimal("10"),
        extraction_confidence=0.9,
        status=BillStatus.READY.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(bill)
    task = PaymentTaskORM(
        task_id="task_test",
        bill_id="bill_test",
        job_id="job_test",
        priority=1,
        status="ready",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(task)
    txn = TransactionORM(
        transaction_id="txn_test",
        task_id="task_test",
        provider_name="Test",
        amount=Decimal("10"),
        confirmation_number="CONF-1",
        verification_status="success",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(txn)
    audit = AuditEventORM(
        event_id="evt_test",
        job_id="job_test",
        bill_id="bill_test",
        task_id="task_test",
        event_type="bill_parsed",
        actor="system",
        timestamp=datetime.utcnow(),
        details_json="{}",
    )
    session.add(audit)
    session.commit()


def test_clear_bills_removes_bills_and_tasks():
    init_db()
    session = get_session()
    clear_workspace(session)
    _seed(session)
    result = clear_bills(session)
    assert result["bills"] == 1
    assert session.query(BillORM).count() == 0
    assert session.query(PaymentTaskORM).count() == 0
    session.close()


def test_clear_report_removes_audit_and_transactions():
    init_db()
    session = get_session()
    clear_workspace(session)
    _seed(session)
    result = clear_report(session)
    assert result["audit_events"] >= 1
    assert session.query(TransactionORM).count() == 0
    assert session.query(BillORM).count() == 1
    session.close()


def test_clear_workspace_removes_all():
    init_db()
    session = get_session()
    clear_workspace(session)
    _seed(session)
    result = clear_workspace(session)
    assert result["jobs"] == 1
    assert session.query(JobORM).count() == 0
    assert session.query(BillORM).count() == 0
    session.close()
