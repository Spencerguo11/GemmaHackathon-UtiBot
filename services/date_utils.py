"""Deterministic date parsing to guard against LLM date-normalization errors.

Vision/text models sometimes "normalize" a date to YYYY-MM-DD but hallucinate
the year in the process, even though the raw printed text they quote as
evidence is correct. Regex-parsing the raw evidence text is far more
reliable than trusting a model's own reformatting.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

_DATE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("%Y-%m-%d", re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b")),
    ("%m/%d/%Y", re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")),
    ("%m/%d/%y", re.compile(r"\b\d{1,2}/\d{1,2}/\d{2}\b")),
    ("%m-%d-%Y", re.compile(r"\b\d{1,2}-\d{1,2}-\d{4}\b")),
    ("%B %d, %Y", re.compile(r"\b[A-Za-z]+ \d{1,2},? \d{4}\b")),
    ("%b %d, %Y", re.compile(r"\b[A-Za-z]{3} \d{1,2},? \d{4}\b")),
]


def parse_date_from_text(text: Optional[str]) -> Optional[str]:
    """Find and normalize the first date-like substring in raw text to YYYY-MM-DD."""
    if not text:
        return None
    text = str(text).strip()
    for fmt, pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(0).replace(",", ",")
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def resolve_date_field(model_value: Optional[str], evidence_text: Optional[str] = None) -> Optional[str]:
    """
    Resolve a date field, preferring a date parsed from raw evidence text
    (deterministic) over the model's own normalized value (error-prone).
    """
    from_evidence = parse_date_from_text(evidence_text)
    if from_evidence:
        return from_evidence
    return parse_date_from_text(model_value)
