#!/usr/bin/env python3
"""Start the Utility Coordinator web application."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn

from config import get_settings

settings = get_settings()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "web.server:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
