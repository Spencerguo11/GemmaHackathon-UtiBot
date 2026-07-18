"""Shared helpers for mock utility provider sites."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone


def generate_confirmation_number() -> str:
    """Generate a mock confirmation number."""
    return f"CONF-{secrets.token_hex(4).upper()}"


def confirmation_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


BASE_STYLE = """
body { font-family: Georgia, serif; margin: 0; background: #f7f7f7; color: #222; }
.container { max-width: 720px; margin: 40px auto; background: white; padding: 32px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.08); }
h1 { margin-top: 0; }
label { display: block; margin-top: 16px; font-weight: bold; }
input, select, button { margin-top: 8px; padding: 10px; font-size: 16px; }
button { background: #005bbb; color: white; border: 0; border-radius: 6px; cursor: pointer; }
.success { color: #0a7a0a; font-size: 1.2rem; }
.meta { margin-top: 12px; }
"""
