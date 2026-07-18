#!/usr/bin/env python3
"""Initialize database."""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    engine = init_db()
    print(f"✅ Database initialized successfully!")
