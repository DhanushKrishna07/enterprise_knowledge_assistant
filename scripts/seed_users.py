#!/usr/bin/env python
"""
scripts/seed_users.py — Seed demo users into the SQLite database.

Usage:
    python scripts/seed_users.py
"""

import sys
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.service import seed_demo_users
from app.core.logging import setup_logging

if __name__ == "__main__":
    setup_logging()
    seed_demo_users()
    print("\nDemo credentials:")
    print("  admin@example.com    / admin123    (role=admin)")
    print("  employee@example.com / employee123 (role=employee)")
    print("  hr@example.com       / hr123       (role=employee, department=hr)")
