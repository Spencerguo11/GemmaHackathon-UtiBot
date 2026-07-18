"""Database repositories for data access."""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4
from sqlalchemy.orm import Session
from database.orm_models import JobORM, BillORM, PaymentTaskORM, TransactionORM, AuditEventORM
from models import Bill, BillStatus, PaymentTask, TaskStatus, Transaction, AuditEvent, EventType, UtilityType
from models.workflow import Job


class JobRepository:
    """Repository for job management."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, total_files: int = 0) -> str:
        """Create new job and return job_id."""
        job_id = f"job_{uuid4().hex[:12]}"
        job = JobORM(
            job_id=job_id,
            status="processing",
            uploaded_at=datetime.utcnow(),
            total_files=total_files,
        )
        self.session.add(job)
        self.session.commit()
        return job_id

    def get(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        job = self.session.query(JobORM).filter(JobORM.job_id == job_id).first()
        if not job:
            return None
        return Job(
            job_id=job.job_id,
            status=job.status,
            uploaded_at=job.uploaded_at,
            completed_at=job.completed_at,
            total_files=job.total_files,
            processed_files=job.processed_files,
            error_message=job.error_message,
        )

    def list_recent(self, limit: int = 10) -> List[str]:
        """Return recent job IDs."""
        jobs = (
            self.session.query(JobORM.job_id)
            .order_by(JobORM.uploaded_at.desc())
            .limit(limit)
            .all()
        )
        return [job.job_id for job in jobs]

    def update_status(self, job_id: str, status: str, error_message: Optional[str] = None):
        """Update job status."""
        job = self.session.query(JobORM).filter(JobORM.job_id == job_id).first()
        if job:
            job.status = status
            if error_message:
                job.error_message = error_message
            if status == "completed":
                job.completed_at = datetime.utcnow()
            self.session.commit()


class BillRepository:
    """Repository for bill management."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, bill: Bill) -> str:
        """Create new bill and return bill_id."""
        bill_id = f"bill_{uuid4().hex[:12]}"
        bill_orm = BillORM(
            bill_id=bill_id,
            job_id=bill.job_id,
            source_filename=bill.source_filename,
            file_hash=bill.file_hash,
            provider_name=bill.provider_name,
            utility_type=bill.utility_type.value,
            account_number_masked=bill.account_number_masked,
            service_address=bill.service_address,
            billing_period_start=bill.billing_period_start,
            billing_period_end=bill.billing_period_end,
            statement_date=bill.statement_date,
            due_date=bill.due_date,
            previous_balance=bill.previous_balance,
            current_charges=bill.current_charges,
            amount_due=bill.amount_due,
            document_payment_url=bill.document_payment_url,
            verified_payment_url=bill.verified_payment_url,
            extraction_confidence=bill.extraction_confidence,
            status=bill.status.value,
            requires_review=bill.requires_review,
            review_reason=bill.review_reason,
            created_at=bill.created_at,
            updated_at=bill.updated_at,
        )
        self.session.add(bill_orm)
        self.session.commit()
        return bill_id

    def get(self, bill_id: str) -> Optional[Bill]:
        """Get bill by ID."""
        bill_orm = self.session.query(BillORM).filter(BillORM.bill_id == bill_id).first()
        if not bill_orm:
            return None
        return self._orm_to_model(bill_orm)

    def get_by_job(self, job_id: str) -> List[Bill]:
        """Get all bills for a job."""
        bills = self.session.query(BillORM).filter(BillORM.job_id == job_id).all()
        return [self._orm_to_model(b) for b in bills]

    def get_by_hash(self, file_hash: str) -> Optional[Bill]:
        """Get bill by file hash."""
        bill_orm = self.session.query(BillORM).filter(BillORM.file_hash == file_hash).first()
        if not bill_orm:
            return None
        return self._orm_to_model(bill_orm)

    def list_all(self) -> List[Bill]:
        """Get all bills ordered by due date."""
        bills = self.session.query(BillORM).order_by(BillORM.due_date.asc()).all()
        return [self._orm_to_model(b) for b in bills]

    def update(self, bill_id: str, **kwargs):
        """Update bill fields."""
        bill = self.session.query(BillORM).filter(BillORM.bill_id == bill_id).first()
        if bill:
            for key, value in kwargs.items():
                if hasattr(bill, key):
                    setattr(bill, key, value)
            bill.updated_at = datetime.utcnow()
            self.session.commit()

    def _orm_to_model(self, bill_orm: BillORM) -> Bill:
        """Convert ORM to Pydantic model."""
        return Bill(
            bill_id=bill_orm.bill_id,
            job_id=bill_orm.job_id,
            source_filename=bill_orm.source_filename,
            file_hash=bill_orm.file_hash,
            provider_name=bill_orm.provider_name,
            utility_type=UtilityType(bill_orm.utility_type),
            account_number_masked=bill_orm.account_number_masked,
            service_address=bill_orm.service_address,
            billing_period_start=bill_orm.billing_period_start,
            billing_period_end=bill_orm.billing_period_end,
            statement_date=bill_orm.statement_date,
            due_date=bill_orm.due_date,
            previous_balance=Decimal(str(bill_orm.previous_balance)),
            current_charges=Decimal(str(bill_orm.current_charges)),
            amount_due=Decimal(str(bill_orm.amount_due)),
            document_payment_url=bill_orm.document_payment_url,
            verified_payment_url=bill_orm.verified_payment_url,
            extraction_confidence=bill_orm.extraction_confidence,
            status=BillStatus(bill_orm.status),
            requires_review=bill_orm.requires_review,
            review_reason=bill_orm.review_reason,
            created_at=bill_orm.created_at,
            updated_at=bill_orm.updated_at,
        )


class PaymentTaskRepository:
    """Repository for payment task management."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, task: PaymentTask) -> str:
        """Create new task and return task_id."""
        task_id = f"task_{uuid4().hex[:12]}"
        task_orm = PaymentTaskORM(
            task_id=task_id,
            bill_id=task.bill_id,
            job_id=task.job_id,
            priority=task.priority,
            status=task.status.value,
            approved_at=task.approved_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            failure_reason=task.failure_reason,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self.session.add(task_orm)
        self.session.commit()
        return task_id

    def get(self, task_id: str) -> Optional[PaymentTask]:
        """Get task by ID."""
        task_orm = self.session.query(PaymentTaskORM).filter(PaymentTaskORM.task_id == task_id).first()
        if not task_orm:
            return None
        return self._orm_to_model(task_orm)

    def get_by_bill(self, bill_id: str) -> Optional[PaymentTask]:
        """Get task for a bill."""
        task_orm = self.session.query(PaymentTaskORM).filter(PaymentTaskORM.bill_id == bill_id).first()
        if not task_orm:
            return None
        return self._orm_to_model(task_orm)

    def get_by_job(self, job_id: str) -> List[PaymentTask]:
        """Get all tasks for a job."""
        tasks = self.session.query(PaymentTaskORM).filter(PaymentTaskORM.job_id == job_id).all()
        return [self._orm_to_model(t) for t in tasks]

    def list_all(self) -> List[PaymentTask]:
        """Get all tasks ordered by priority."""
        tasks = self.session.query(PaymentTaskORM).order_by(PaymentTaskORM.priority.asc()).all()
        return [self._orm_to_model(t) for t in tasks]

    def update(self, task_id: str, **kwargs):
        """Update task fields."""
        task = self.session.query(PaymentTaskORM).filter(PaymentTaskORM.task_id == task_id).first()
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.utcnow()
            self.session.commit()

    def _orm_to_model(self, task_orm: PaymentTaskORM) -> PaymentTask:
        """Convert ORM to Pydantic model."""
        return PaymentTask(
            task_id=task_orm.task_id,
            bill_id=task_orm.bill_id,
            job_id=task_orm.job_id,
            priority=task_orm.priority,
            status=TaskStatus(task_orm.status),
            approved_at=task_orm.approved_at,
            started_at=task_orm.started_at,
            completed_at=task_orm.completed_at,
            failure_reason=task_orm.failure_reason,
            created_at=task_orm.created_at,
            updated_at=task_orm.updated_at,
        )



class TransactionRepository:
    """Repository for payment transactions."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, transaction: Transaction) -> str:
        transaction_id = f"txn_{uuid4().hex[:12]}"
        txn_orm = TransactionORM(
            transaction_id=transaction_id,
            task_id=transaction.task_id,
            provider_name=transaction.provider_name,
            amount=transaction.amount,
            confirmation_number=transaction.confirmation_number,
            submitted_at=transaction.submitted_at,
            verified_at=transaction.verified_at,
            verification_status=transaction.verification_status,
            receipt_path=transaction.receipt_path,
            screenshot_path=transaction.screenshot_path,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at,
        )
        self.session.add(txn_orm)
        self.session.commit()
        return transaction_id

    def list_all(self) -> List[Transaction]:
        txns = self.session.query(TransactionORM).order_by(TransactionORM.created_at.desc()).all()
        return [
            Transaction(
                transaction_id=txn.transaction_id,
                task_id=txn.task_id,
                provider_name=txn.provider_name,
                amount=Decimal(str(txn.amount)),
                confirmation_number=txn.confirmation_number,
                submitted_at=txn.submitted_at,
                verified_at=txn.verified_at,
                verification_status=txn.verification_status,
                receipt_path=txn.receipt_path,
                screenshot_path=txn.screenshot_path,
                created_at=txn.created_at,
                updated_at=txn.updated_at,
            )
            for txn in txns
        ]


class AuditRepository:
    """Repository for audit event management."""

    def __init__(self, session: Session):
        self.session = session

    def log_event(self, event: AuditEvent) -> str:
        """Log audit event."""
        import json

        event_id = f"evt_{uuid4().hex[:12]}"
        event_orm = AuditEventORM(
            event_id=event_id,
            job_id=event.job_id,
            bill_id=event.bill_id,
            task_id=event.task_id,
            event_type=event.event_type.value,
            actor=event.actor,
            timestamp=event.timestamp,
            details_json=json.dumps(event.details_json),
        )
        self.session.add(event_orm)
        self.session.commit()
        return event_id

    def get_by_job(self, job_id: str) -> List[AuditEvent]:
        """Get audit events for a job."""
        events = self.session.query(AuditEventORM).filter(AuditEventORM.job_id == job_id).all()
        return [self._orm_to_model(e) for e in events]

    def list_recent(self, limit: int = 100) -> List[AuditEvent]:
        """Get recent audit events."""
        events = (
            self.session.query(AuditEventORM)
            .order_by(AuditEventORM.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [self._orm_to_model(e) for e in events]

    def _orm_to_model(self, event_orm: AuditEventORM) -> AuditEvent:
        """Convert ORM to Pydantic model."""
        import json
        return AuditEvent(
            event_id=event_orm.event_id,
            job_id=event_orm.job_id,
            bill_id=event_orm.bill_id,
            task_id=event_orm.task_id,
            event_type=EventType(event_orm.event_type),
            actor=event_orm.actor,
            timestamp=event_orm.timestamp,
            details_json=json.loads(event_orm.details_json),
        )
