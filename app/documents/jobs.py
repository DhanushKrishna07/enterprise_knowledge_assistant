"""
app/documents/jobs.py — Ingestion job state tracking (SQLite-backed).

States: queued → extracting → ocr → chunking → embedding → indexing → completed | failed
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# SQLite database path is set when the module is first used
_DB_PATH: str = "data/app.db"


def set_db_path(path: str) -> None:
    global _DB_PATH
    _DB_PATH = path


def _connect() -> sqlite3.Connection:
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables() -> None:
    """Create ingestion tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'running',
            files_seen INTEGER DEFAULT 0,
            files_added INTEGER DEFAULT 0,
            files_updated INTEGER DEFAULT 0,
            files_skipped INTEGER DEFAULT 0,
            files_failed INTEGER DEFAULT 0,
            chunks_added INTEGER DEFAULT 0,
            ocr_pages INTEGER DEFAULT 0,
            tables_extracted INTEGER DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            details_json TEXT
        );

        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            filename TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            stage TEXT DEFAULT '',
            progress REAL DEFAULT 0.0,
            error TEXT DEFAULT '',
            chunks_added INTEGER DEFAULT 0,
            ocr_pages INTEGER DEFAULT 0,
            tables_extracted INTEGER DEFAULT 0,
            started_at TEXT,
            finished_at TEXT,
            details_json TEXT,
            FOREIGN KEY(run_id) REFERENCES ingestion_runs(id)
        );
        """)


class JobStatus(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    OCR = "ocr"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class IngestionJob:
    id: str
    run_id: str
    filename: str
    status: str = JobStatus.QUEUED
    stage: str = ""
    progress: float = 0.0
    error: str = ""
    chunks_added: int = 0
    ocr_pages: int = 0
    tables_extracted: int = 0
    started_at: str = field(default_factory=lambda: _now())
    finished_at: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("details", None)
        d["details_json"] = json.dumps(self.details)
        return d


def create_run(run_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ingestion_runs (id, status, started_at) VALUES (?, 'running', ?)",
            (run_id, _now()),
        )


def update_run(run_id: str, **kwargs: Any) -> None:
    if not kwargs:
        return
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [run_id]
    with _connect() as conn:
        conn.execute(f"UPDATE ingestion_runs SET {cols} WHERE id = ?", vals)


def upsert_job(job: IngestionJob) -> None:
    d = job.to_dict()
    cols = ", ".join(d.keys())
    placeholders = ", ".join("?" for _ in d)
    with _connect() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO ingestion_jobs ({cols}) VALUES ({placeholders})",
            list(d.values()),
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
        if row:
            return dict(row)
    return None


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM ingestion_runs WHERE id = ?", (run_id,)).fetchone()
        if row:
            return dict(row)
    return None


def list_jobs(run_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ingestion_jobs WHERE run_id = ? ORDER BY started_at",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
