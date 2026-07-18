"""Restricted Playwright action execution."""
from __future__ import annotations

import logging
from decimal import Decimal

from models import BrowserAction
from services.provider_service import is_trusted_payment_url

logger = logging.getLogger(__name__)


class ActionExecutionError(Exception):
    """Raised when a browser action cannot be executed safely."""


def resolve_value(reference: str | None, bill) -> str:
    """Resolve bill value references like bill.amount_due."""
    if not reference:
        return ""
    mapping = {
        "bill.account_number_masked": bill.account_number_masked.replace("*", ""),
        "bill.amount_due": f"{bill.amount_due:.2f}",
        "bill.provider_name": bill.provider_name,
    }
    return mapping.get(reference, reference)


def execute_action(page, action: BrowserAction, bill, *, approved: bool = False) -> None:
    """Execute one structured browser action with safety checks."""
    if action.action == "OPEN_URL":
        if not action.target or not is_trusted_payment_url(action.target):
            raise ActionExecutionError(f"Untrusted domain blocked: {action.target}")
        page.goto(action.target, wait_until="domcontentloaded")
        return

    if action.action == "CLICK":
        if action.requires_confirmation and not approved:
            raise ActionExecutionError("Click requires explicit human approval")
        page.click(action.target or "")
        return

    if action.action == "FILL":
        value = resolve_value(action.value_reference, bill)
        page.fill(action.target or "", value)
        return

    if action.action == "WAIT":
        page.wait_for_timeout(int(action.target or "500"))
        return

    if action.action == "SCREENSHOT":
        page.screenshot(path=action.target or "screenshot.png")
        return

    if action.action in {"REQUEST_HUMAN", "STOP"}:
        raise ActionExecutionError(action.reason or "Human intervention required")

    raise ActionExecutionError(f"Unsupported action: {action.action}")
