"""Configuration package."""
from .settings import Settings, get_settings, PROJECT_ROOT, DATA_DIR, JOBS_DIR, SCREENSHOTS_DIR, RECEIPTS_DIR

__all__ = [
    "Settings",
    "get_settings",
    "PROJECT_ROOT",
    "DATA_DIR",
    "JOBS_DIR",
    "SCREENSHOTS_DIR",
    "RECEIPTS_DIR",
]
