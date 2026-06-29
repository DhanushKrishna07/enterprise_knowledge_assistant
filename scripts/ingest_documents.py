#!/usr/bin/env python
"""
scripts/ingest_documents.py — CLI ingestion script.

Usage:
    python scripts/ingest_documents.py data/documents
    python scripts/ingest_documents.py path/to/file.pdf
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from app.core.logging import get_logger, setup_logging
from app.documents.jobs import init_tables
from app.indexing.ingest_service import ingest_directory, ingest_file

logger = get_logger(__name__)


@click.command()
@click.argument("path", default="data/documents")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output.")
def main(path: str, verbose: bool) -> None:
    """Ingest documents from PATH (file or directory) into the knowledge base."""
    setup_logging()
    init_tables()

    p = Path(path)
    if not p.exists():
        click.echo(f"Error: path not found: {p}", err=True)
        sys.exit(1)

    if p.is_file():
        click.echo(f"Ingesting file: {p.name}")
        result = ingest_file(p)
        click.echo(f"Done: {result}")
    elif p.is_dir():
        click.echo(f"Ingesting directory: {p}")
        report = ingest_directory(p)
        _print_report(report, verbose)
    else:
        click.echo(f"Error: {p} is not a file or directory.", err=True)
        sys.exit(1)


def _print_report(report, verbose: bool) -> None:
    s = report.summary()
    click.echo("\n" + "=" * 50)
    click.echo("INGESTION REPORT")
    click.echo("=" * 50)
    click.echo(f"Run ID       : {s['run_id']}")
    click.echo(f"Files seen   : {s['files_seen']}")
    click.echo(f"  Added      : {s['files_added']}")
    click.echo(f"  Updated    : {s['files_updated']}")
    click.echo(f"  Skipped    : {s['files_skipped']}")
    click.echo(f"  Failed     : {s['files_failed']}")
    click.echo(f"Chunks added : {s['chunks_added']}")
    click.echo(f"OCR pages    : {s['ocr_pages']}")
    click.echo(f"Tables       : {s['tables_extracted']}")
    if s["warnings"] and verbose:
        click.echo("\nWarnings:")
        for w in s["warnings"]:
            click.echo(f"  ⚠ {w}")
    if s["errors"]:
        click.echo("\nErrors:")
        for e in s["errors"]:
            click.echo(f"  ✗ {e}", err=True)


def show_status() -> None:
    """Print status of the latest ingestion run."""
    setup_logging()
    from app.documents.jobs import _connect

    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if row:
            print(dict(row))
        else:
            print("No ingestion runs found.")


if __name__ == "__main__":
    main()
