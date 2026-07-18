"""Test provider registry resolution."""
from services.provider_service import get_trusted_payment_url, resolve_provider


def test_resolve_provider_by_alias():
    entry = resolve_provider("Rocky Mountain Power")
    assert entry is not None
    assert entry["canonical_name"] == "Rocky Mountain Power Demo"


def test_trusted_payment_url_from_registry():
    url = get_trusted_payment_url("Dominion Energy")
    assert url == "http://localhost:8002/pay"


def test_unknown_provider_returns_none():
    assert resolve_provider("Unknown Utility Co") is None
