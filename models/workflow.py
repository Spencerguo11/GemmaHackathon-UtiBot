"""Workflow models."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class Job(BaseModel):
    """Batch job model."""
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    uploaded_at: datetime
    completed_at: Optional[datetime] = None
    total_files: int = 0
    processed_files: int = 0
    error_message: Optional[str] = None


class ProcessingResult(BaseModel):
    """Result of batch processing."""
    job_id: str
    bills_created: int
    bills_needing_review: int
    duplicates_detected: int
    errors: list[str] = []
