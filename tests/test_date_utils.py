"""Tests for deterministic date parsing helpers."""
from services.date_utils import parse_date_from_text, resolve_date_field


def test_parse_date_from_text_slash_format():
    assert parse_date_from_text("7/15/2026") == "2026-07-15"


def test_parse_date_from_text_iso_format():
    assert parse_date_from_text("2026-07-15") == "2026-07-15"


def test_parse_date_from_text_two_digit_year():
    assert parse_date_from_text("06/30/26") == "2026-06-30"


def test_parse_date_from_text_none_or_empty():
    assert parse_date_from_text(None) is None
    assert parse_date_from_text("") is None
    assert parse_date_from_text("no date here") is None


def test_resolve_date_field_prefers_evidence_over_model_value():
    # Model hallucinated the year (2022) but evidence has the correct raw text.
    assert resolve_date_field("2022-07-14", "7/14/2026") == "2026-07-14"


def test_resolve_date_field_falls_back_to_model_value():
    assert resolve_date_field("2026-07-14", None) == "2026-07-14"


def test_resolve_date_field_both_missing():
    assert resolve_date_field(None, None) is None
