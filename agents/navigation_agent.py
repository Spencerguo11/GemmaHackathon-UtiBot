"""Navigation agent returning one structured browser action."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from models import BrowserAction, PageObservation

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = {
    "OPEN_URL",
    "CLICK",
    "FILL",
    "SELECT",
    "WAIT",
    "SCREENSHOT",
    "REQUEST_HUMAN",
    "STOP",
}


def detect_stop_condition(observation: PageObservation) -> BrowserAction | None:
    """Stop when unsafe page conditions are detected."""
    text = observation.visible_text.lower()
    if "captcha" in text:
        return BrowserAction(action="STOP", reason="CAPTCHA detected", requires_confirmation=False)
    if "multi-factor" in text or "mfa" in text:
        return BrowserAction(action="STOP", reason="MFA detected", requires_confirmation=False)

    host = urlparse(observation.url).netloc.lower()
    if host and "localhost" not in host and "127.0.0.1" not in host:
        return BrowserAction(action="STOP", reason=f"Unexpected domain: {host}", requires_confirmation=False)
    return None


def next_electric_action(observation: PageObservation, step: int, payment_url: str) -> BrowserAction:
    """Deterministic navigation plan for Rocky Mountain Power Demo."""
    if step == 0:
        return BrowserAction(
            action="OPEN_URL",
            target=payment_url,
            reason="Open trusted electric provider payment page",
        )
    if "account number" in observation.visible_text.lower() and step <= 2:
        return BrowserAction(
            action="FILL",
            target="#account_number",
            value_reference="bill.account_number_masked",
            reason="Enter account number",
        )
    if step <= 3 and observation.url.endswith("/pay"):
        return BrowserAction(action="CLICK", target="#continue", reason="Continue to amount step")
    if "payment amount" in observation.visible_text.lower():
        return BrowserAction(
            action="FILL",
            target="#payment_amount",
            value_reference="bill.amount_due",
            reason="Enter payment amount",
        )
    if "review your payment" in observation.visible_text.lower():
        return BrowserAction(
            action="CLICK",
            target="#submit_payment",
            reason="Submit mock payment after approval",
            requires_confirmation=True,
        )
    if "payment successful" in observation.visible_text.lower():
        return BrowserAction(action="SCREENSHOT", target="", reason="Capture confirmation page")
    return BrowserAction(action="WAIT", target="500", reason="Wait for page update")


def choose_next_action(
    observation: PageObservation,
    *,
    goal: str,
    step: int,
    payment_url: str,
    action_history: list[str] | None = None,
) -> BrowserAction:
    """Choose the next safe browser action."""
    action_history = action_history or []
    if len(action_history) >= 15:
        return BrowserAction(action="STOP", reason="Maximum browser steps reached")

    if len(action_history) >= 3 and len(set(action_history[-3:])) == 1:
        return BrowserAction(action="STOP", reason="Loop detected in browser actions")

    stop = detect_stop_condition(observation)
    if stop:
        return stop

    if "electric" in goal.lower() or "rocky mountain" in goal.lower():
        return next_electric_action(observation, step, payment_url)

    return BrowserAction(action="REQUEST_HUMAN", reason="Unsupported provider flow requires human help")
