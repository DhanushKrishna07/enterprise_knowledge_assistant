#!/usr/bin/env python
"""
scripts/export_feedback.py — Export user feedback to CSV.

Usage:
    python scripts/export_feedback.py
    python scripts/export_feedback.py --out data/exports/feedback.csv
"""

import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from app.core.config import get_settings


@click.command()
@click.option("--out", default="data/exports/feedback.csv", help="Output CSV path.")
def main(out: str) -> None:
    """Export all feedback records to a CSV file."""
    settings = get_settings()
    db_path = settings.sqlite_url.replace("sqlite:///", "")

    if not Path(db_path).exists():
        click.echo("No database found. Run the app and collect feedback first.", err=True)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM feedback ORDER BY created_at DESC").fetchall()
    conn.close()

    if not rows:
        click.echo("No feedback records found.")
        return

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=dict(rows[0]).keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])

    click.echo(f"Exported {len(rows)} feedback records to {out_path}")


if __name__ == "__main__":
    main()
