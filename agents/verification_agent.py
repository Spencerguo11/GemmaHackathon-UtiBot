"""Verification agent for mock payment confirmations."""
from __future__ import annotations

import re
from decimal import Decimal

from models import Bill


class VerificationResult:
    def __init__(
        self,
        success: bool,
        confirmation_number: str | None = None,
        confirmed_amount: Decimal | None = None,
        provider_name: str | None = None,
        failure_reason: str | None = None,
    ):
        self.success = success
        self.confirmation_number = confirmation_number
        self.confirmed_amount = confirmed_amount
        self.provider_name = provider_name
        self.failure_reason = failure_reason


def verify_confirmation_page(page_text: str, bill: Bill) -> VerificationResult:
    """Verify confirmation details against intended bill payment."""
    text = page_text or ""
    lower = text.lower()

    if "payment successful" not in lower:
        return VerificationResult(success=False, failure_reason="Success message not found")

    confirmation_match = re.search(r"CONF-[A-F0-9]{8}", text)
    if not confirmation_match:
        return VerificationResult(success=False, failure_reason="Confirmation number missing")
    confirmation_number = confirmation_match.group(0)

    amount_match = re.search(r"Paid amount:\s*\$?([0-9]+(?:\.[0-9]{2})?)", text, re.IGNORECASE)
    if not amount_match:
        return VerificationResult(success=False, failure_reason="Confirmed amount missing")
    confirmed_amount = Decimal(amount_match.group(1))

    provider_match = re.search(r"Provider:\s*(.+)", text, re.IGNORECASE)
    provider_name = provider_match.group(1).strip() if provider_match else bill.provider_name

    if confirmed_amount != bill.amount_due:
        return VerificationResult(
            success=False,
            confirmation_number=confirmation_number,
            confirmed_amount=confirmed_amount,
            provider_name=provider_name,
            failure_reason=f"Amount mismatch: expected {bill.amount_due}, got {confirmed_amount}",
        )

    if bill.provider_name.lower() not in provider_name.lower() and provider_name.lower() not in bill.provider_name.lower():
        return VerificationResult(
            success=False,
            confirmation_number=confirmation_number,
            confirmed_amount=confirmed_amount,
            provider_name=provider_name,
            failure_reason="Provider mismatch",
        )

    return VerificationResult(
        success=True,
        confirmation_number=confirmation_number,
        confirmed_amount=confirmed_amount,
        provider_name=provider_name,
    )
