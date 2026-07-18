"""Pydantic models for core domain objects."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class BillStatus(str, Enum):
    """Bill processing status."""
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    PAYMENT_PREPARED = "payment_prepared"
    AWAITING_APPROVAL = "awaiting_approval"
    PAID = "paid"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class TaskStatus(str, Enum):
    """Payment task status."""
    CREATED = "created"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UtilityType(str, Enum):
    """Utility types."""
    ELECTRICITY = "electricity"
    GAS = "gas"
    WATER = "water"
    OTHER = "other"


class EventType(str, Enum):
    """Audit event types."""
    JOB_CREATED = "job_created"
    ZIP_VALIDATED = "zip_validated"
    PDF_EXTRACTED = "pdf_extracted"
    BILL_PARSED = "bill_parsed"
    BILL_VALIDATION_PASSED = "bill_validation_passed"
    BILL_FLAGGED_FOR_REVIEW = "bill_flagged_for_review"
    DUPLICATE_DETECTED = "duplicate_detected"
    TASK_CREATED = "task_created"
    BROWSER_FLOW_STARTED = "browser_flow_started"
    HUMAN_APPROVAL_REQUESTED = "human_approval_requested"
    HUMAN_APPROVAL_GRANTED = "human_approval_granted"
    PAYMENT_SUBMITTED = "payment_submitted"
    PAYMENT_VERIFIED = "payment_verified"
    PAYMENT_FAILED = "payment_failed"


class BillExtraction(BaseModel):
    """Extracted bill information from LLM."""
    provider_name: Optional[str] = None
    utility_type: Optional[str] = None
    account_number_masked: Optional[str] = None
    service_address: Optional[str] = None
    billing_period_start: Optional[str] = None
    billing_period_end: Optional[str] = None
    statement_date: Optional[str] = None
    due_date: Optional[str] = None
    previous_balance: Optional[Decimal] = None
    current_charges: Optional[Decimal] = None
    amount_due: Optional[Decimal] = None
    document_payment_url: Optional[str] = None
    extraction_confidence: float = 0.0
    evidence: dict = Field(default_factory=dict)

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else None
        }


class Bill(BaseModel):
    """Utility bill model."""
    bill_id: str
    job_id: str
    source_filename: str
    file_hash: str
    provider_name: str
    utility_type: UtilityType
    account_number_masked: str
    service_address: str
    billing_period_start: str  # YYYY-MM-DD
    billing_period_end: str  # YYYY-MM-DD
    statement_date: str  # YYYY-MM-DD
    due_date: str  # YYYY-MM-DD
    previous_balance: Decimal = Decimal("0.00")
    current_charges: Decimal
    amount_due: Decimal
    document_payment_url: Optional[str] = None
    verified_payment_url: Optional[str] = None
    extraction_confidence: float
    status: BillStatus = BillStatus.EXTRACTED
    requires_review: bool = False
    review_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("amount_due", "current_charges", "previous_balance", mode="before")
    @classmethod
    def ensure_decimal(cls, v):
        if v is None:
            return Decimal("0.00")
        return Decimal(str(v)) if not isinstance(v, Decimal) else v

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat(),
        }


class PaymentTask(BaseModel):
    """Payment task model."""
    task_id: str
    bill_id: str
    job_id: str
    priority: int  # Lower = higher priority
    status: TaskStatus = TaskStatus.CREATED
    approved_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class Transaction(BaseModel):
    """Payment transaction model."""
    transaction_id: str
    task_id: str
    provider_name: str
    amount: Decimal
    confirmation_number: Optional[str] = None
    submitted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verification_status: Optional[str] = None  # "success", "failed", "needs_review"
    receipt_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("amount", mode="before")
    @classmethod
    def ensure_decimal(cls, v):
        return Decimal(str(v)) if not isinstance(v, Decimal) else v

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat() if v else None,
        }


class AuditEvent(BaseModel):
    """Audit event model."""
    event_id: str
    job_id: str
    bill_id: Optional[str] = None
    task_id: Optional[str] = None
    event_type: EventType
    actor: str  # "system", "user", "browser_automation"
    timestamp: datetime
    details_json: dict = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class BrowserAction(BaseModel):
    """Structured browser action."""
    action: str  # OPEN_URL, CLICK, FILL, SELECT, WAIT, SCREENSHOT, REQUEST_HUMAN, STOP
    target: Optional[str] = None  # URL, element ID, etc.
    value_reference: Optional[str] = None  # bill.account_number_masked, etc.
    reason: str
    requires_confirmation: bool = False


class PageObservation(BaseModel):
    """Sanitized page observation."""
    url: str
    title: str
    visible_text: str
    interactive_elements: list[dict] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "url": "http://localhost:8001/pay",
                "title": "Rocky Mountain Power Demo",
                "visible_text": "Pay your utility bill",
                "interactive_elements": [
                    {
                        "id": "el_1",
                        "role": "textbox",
                        "label": "Account number"
                    }
                ]
            }
        }
