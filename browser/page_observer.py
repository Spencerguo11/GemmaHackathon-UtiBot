"""Sanitized Playwright page observation."""
from __future__ import annotations

import re
from typing import Any

from models import PageObservation


def _label_for(element) -> str:
    aria = element.get_attribute("aria-label")
    if aria:
        return aria.strip()
    element_id = element.get_attribute("id")
    if element_id:
        return element_id.replace("_", " ").strip()
    name = element.get_attribute("name")
    if name:
        return name.replace("_", " ").strip()
    text = (element.inner_text() or "").strip()
    return text[:80] if text else "interactive element"


def observe_page(page) -> PageObservation:
    """Build a sanitized page representation for agents."""
    visible_text = re.sub(r"\s+", " ", (page.inner_text("body") or "")).strip()[:1200]
    interactive_elements: list[dict[str, Any]] = []

    selectors = "input, select, textarea, button, a[href]"
    for index, element in enumerate(page.query_selector_all(selectors), start=1):
        role = element.evaluate(
            "el => el.tagName.toLowerCase() === 'a' ? 'link' : (el.type || el.tagName.toLowerCase())"
        )
        interactive_elements.append(
            {
                "id": f"el_{index}",
                "role": role,
                "label": _label_for(element),
            }
        )

    return PageObservation(
        url=page.url,
        title=page.title(),
        visible_text=visible_text,
        interactive_elements=interactive_elements,
    )
