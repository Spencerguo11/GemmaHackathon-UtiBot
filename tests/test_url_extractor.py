"""Tests for payment URL extraction."""
from services.url_extractor import extract_payment_urls, pick_best_payment_url


def test_extract_payment_urls_prefers_pay_links():
    text = "Visit https://pay.example.com/bill and also https://example.com/help"
    urls = extract_payment_urls(text)
    assert urls[0].startswith("https://pay.example.com")


def test_pick_best_payment_url_uses_model_value_first():
    text = "Pay at https://pay.example.com/now"
    assert pick_best_payment_url(text, "https://model.example.com/pay") == "https://model.example.com/pay"
