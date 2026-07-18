#!/usr/bin/env python3
"""Run all mock utility provider websites."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uvicorn


def run_server(module: str, port: int) -> None:
    uvicorn.run(f"{module}:app", host="127.0.0.1", port=port, log_level="warning")


def main() -> None:
    servers = [
        ("mock_providers.electric_provider", 8001),
        ("mock_providers.gas_provider", 8002),
        ("mock_providers.water_provider", 8003),
    ]
    for module, port in servers:
        thread = threading.Thread(target=run_server, args=(module, port), daemon=True)
        thread.start()
        print(f"Started {module} on http://127.0.0.1:{port}/pay")

    print("Mock providers running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping mock providers.")


if __name__ == "__main__":
    main()
