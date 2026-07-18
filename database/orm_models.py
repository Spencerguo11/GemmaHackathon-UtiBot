"""SQLAlchemy ORM models."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Float, Text, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, Session
from typing import Optional

Base = declarative_base()


class JobORM(Base):
    """Job table."""
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True)
    status = Column(String(32), nullable=False)  # pending, processing, completed, failed
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    bills = relationship("BillORM", back_populates="job", cascade="all, delete-orphan")
    tasks = relationship("PaymentTaskORM", back_populates="job", cascade="all, delete-orphan")
    audit_events = relationship("AuditEventORM", back_populates="job", cascade="all, delete-orphan")


class BillORM(Base):
    """Bill table."""
    __tablename__ = "bills"

    bill_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("jobs.job_id"), nullable=False)
    source_filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    provider_name = Column(String(255), nullable=False)
    utility_type = Column(String(32), nullable=False)  # electricity, gas, water, other
    account_number_masked = Column(String(32), nullable=False)
    service_address = Column(String(255), nullable=False)
    billing_period_start = Column(String(10), nullable=False)  # YYYY-MM-DD
    billing_period_end = Column(String(10), nullable=False)  # YYYY-MM-DD
    statement_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    due_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    previous_balance = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    current_charges = Column(Numeric(12, 2), nullable=False)
    amount_due = Column(Numeric(12, 2), nullable=False)
    document_payment_url = Column(String(500), nullable=True)
    verified_payment_url = Column(String(500), nullable=True)
    extraction_confidence = Column(Float, nullable=False)
    status = Column(String(32), nullable=False)  # extracted, needs_review, ready, etc.
    requires_review = Column(Boolean, default=False)
    review_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("JobORM", back_populates="bills")
    task = relationship("PaymentTaskORM", back_populates="bill", uselist=False)
    audit_events = relationship("AuditEventORM", back_populates="bill", cascade="all, delete-orphan")


class PaymentTaskORM(Base):
    """Payment task table."""
    __tablename__ = "payment_tasks"

    task_id = Column(String(64), primary_key=True)
    bill_id = Column(String(64), ForeignKey("bills.bill_id"), nullable=False, unique=True)
    job_id = Column(String(64), ForeignKey("jobs.job_id"), nullable=False)
    priority = Column(Integer, nullable=False)  # Lower = higher priority
    status = Column(String(32), nullable=False)  # created, ready, in_progress, awaiting_approval, completed, failed
    approved_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    bill = relationship("BillORM", back_populates="task")
    job = relationship("JobORM", back_populates="tasks")
    transaction = relationship("TransactionORM", back_populates="task", uselist=False)
    audit_events = relationship("AuditEventORM", back_populates="task", cascade="all, delete-orphan")


class TransactionORM(Base):
    """Payment transaction table."""
    __tablename__ = "transactions"

    transaction_id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("payment_tasks.task_id"), nullable=False, unique=True)
    provider_name = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    confirmation_number = Column(String(64), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verification_status = Column(String(32), nullable=True)  # success, failed, needs_review
    receipt_path = Column(String(500), nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("PaymentTaskORM", back_populates="transaction")


class AuditEventORM(Base):
    """Audit event table."""
    __tablename__ = "audit_events"

    event_id = Column(String(64), primary_key=True)
    job_id = Column(String(64), ForeignKey("jobs.job_id"), nullable=False)
    bill_id = Column(String(64), ForeignKey("bills.bill_id"), nullable=True)
    task_id = Column(String(64), ForeignKey("payment_tasks.task_id"), nullable=True)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(64), nullable=False)  # system, user, browser_automation
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    details_json = Column(Text, nullable=False, default="{}")

    job = relationship("JobORM", back_populates="audit_events")
    bill = relationship("BillORM", back_populates="audit_events")
    task = relationship("PaymentTaskORM", back_populates="audit_events")
