"""
app/auth/service.py — User lookup, creation, and seeding against SQLite.
"""

from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from typing import Any

from app.auth.security import hash_password, verify_password
from app.core.config import get_settings

_DB_PATH: str | None = None


def _db() -> str:
    global _DB_PATH
    if _DB_PATH is None:
        settings = get_settings()
        _DB_PATH = settings.sqlite_url.replace("sqlite:///", "")
    return _DB_PATH


def _connect() -> sqlite3.Connection:
    db = _db()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_user_table() -> None:
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            department TEXT NOT NULL DEFAULT 'general',
            created_at TEXT
        )
        """)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_email(email)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def create_user(
    email: str, password: str, role: str = "employee", department: str = "general"
) -> None:
    init_user_table()
    pw_hash = hash_password(password)
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (email, password_hash, role, department, created_at) VALUES (?, ?, ?, ?, ?)",
            (email, pw_hash, role, department, now),
        )


SEED_USERS = [
    {"email": "admin@example.com", "password": "admin123", "role": "admin", "department": "all"},
    {
        "email": "employee@example.com",
        "password": "employee123",
        "role": "employee",
        "department": "general",
    },
    {"email": "hr@example.com", "password": "hr123", "role": "employee", "department": "hr"},
]


def seed_demo_users() -> None:
    init_user_table()
    for u in SEED_USERS:
        create_user(u["email"], u["password"], u["role"], u["department"])
    print(f"Seeded {len(SEED_USERS)} demo users.")
