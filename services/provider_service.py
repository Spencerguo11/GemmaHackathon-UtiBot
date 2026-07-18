"""Provider registry lookup and trusted payment URL resolution."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import yaml

from config import PROJECT_ROOT

logger = logging.getLogger(__name__)

REGISTRY_PATH = PROJECT_ROOT / "config" / "provider_registry.yaml"


@lru_cache(maxsize=1)
def load_provider_registry() -> dict[str, dict[str, Any]]:
    """Load provider registry from YAML."""
    with open(REGISTRY_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def resolve_provider(provider_name: Optional[str]) -> Optional[dict[str, Any]]:
    """
    Resolve a provider name or alias to registry entry.

    Returns dict with canonical_name, utility_type, payment_url, trusted_domains.
    """
    if not provider_name or not provider_name.strip():
        return None

    target = _normalize_name(provider_name)
    registry = load_provider_registry()

    for entry in registry.values():
        candidates = [entry.get("canonical_name", "")]
        candidates.extend(entry.get("aliases", []))
        for candidate in candidates:
            if _normalize_name(candidate) == target:
                return entry
            if target in _normalize_name(candidate) or _normalize_name(candidate) in target:
                return entry

    return None


def get_trusted_payment_url(provider_name: Optional[str]) -> Optional[str]:
    """Return trusted payment URL from registry; never invent URLs."""
    entry = resolve_provider(provider_name)
    if not entry:
        return None
    return entry.get("payment_url")


def is_trusted_payment_url(url: Optional[str]) -> bool:
    """Check whether a payment URL belongs to a trusted provider domain."""
    if not url:
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.netloc.lower()
    registry = load_provider_registry()
    for entry in registry.values():
        trusted_domains = [d.lower() for d in entry.get("trusted_domains", [])]
        if host in trusted_domains:
            return True
    return False


def get_provider_by_utility_type(utility_type: str) -> Optional[dict[str, Any]]:
    """Find first registry entry matching utility type."""
    registry = load_provider_registry()
    for entry in registry.values():
        if entry.get("utility_type") == utility_type:
            return entry
    return None
