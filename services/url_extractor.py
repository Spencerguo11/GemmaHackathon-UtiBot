"""Extract payment URLs from bill text."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse


PAYMENT_HINTS = (
    "pay",
    "payment",
    "billpay",
    "myaccount",
    "account",
    "portal",
    "online",
)


def extract_payment_urls(text: str) -> list[str]:
    """Find likely pay-online URLs in bill text."""
    if not text:
        return []

    pattern = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
    urls: list[str] = []
    seen: set[str] = set()

    for match in pattern.finditer(text):
        raw = match.group(0).rstrip(".,);]")
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        host_path = f"{parsed.netloc}{parsed.path}".lower()
        if any(hint in host_path for hint in PAYMENT_HINTS):
            if raw not in seen:
                seen.add(raw)
                urls.append(raw)

    if not urls:
        for match in pattern.finditer(text):
            raw = match.group(0).rstrip(".,);]")
            if raw not in seen:
                seen.add(raw)
                urls.append(raw)

    return urls[:5]


def pick_best_payment_url(text: str, model_url: str | None = None) -> str | None:
    """Choose the best payment URL from model output and regex scan."""
    if model_url and model_url.startswith(("http://", "https://")):
        return model_url
    found = extract_payment_urls(text)
    return found[0] if found else None
