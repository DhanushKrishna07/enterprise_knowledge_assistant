#!/usr/bin/env python
"""
scripts/reindex_documents.py — Wipe search indexes and reindex all documents.

Run this after adding or removing files in data/documents/.

Usage:
    python scripts/reindex_documents.py
    python scripts/reindex_documents.py --path data/documents

Stop the API server first if it is running, then restart it after reindex completes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from app.core.config import get_settings
from app.core.deps_check import ensure_dependencies
from app.core.logging import setup_logging
from app.core.ml_preload import preload_ml_stack
from app.documents.jobs import init_tables
from app.indexing.index_reset import clear_search_indexes
from app.indexing.ingest_service import ingest_directory


@click.command()
@click.option(
    "--path",
    "docs_path",
    default=None,
    help="Documents folder (default: DOCUMENTS_PATH from .env)",
)
def main(docs_path: str | None) -> None:
    """Delete existing indexes and rebuild from every file in the documents folder."""
    ensure_dependencies()
    setup_logging()
    settings = get_settings()
    target = Path(docs_path or settings.documents_path)
    target.mkdir(parents=True, exist_ok=True)

    supported = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
    files = sorted(
        f.name for f in target.iterdir() if f.is_file() and f.suffix.lower() in supported
    )

    click.echo("=" * 56)
    click.echo("  REINDEX DOCUMENTS")
    click.echo("=" * 56)
    click.echo(f"Folder : {target.resolve()}")
    click.echo(f"Files  : {len(files)}")
    for name in files:
        click.echo(f"         - {name}")
    click.echo("")
    click.echo("Step 1/3: Clearing Chroma, BM25, checksums, and RAG caches...")
    try:
        clear_search_indexes()
    except Exception as exc:
        click.echo(f"Failed to clear indexes: {exc}", err=True)
        click.echo("Tip: stop the API server and run this script again.", err=True)
        sys.exit(1)

    click.echo("Step 2/3: Preloading ML libraries...")
    preload_ml_stack()

    click.echo("Step 3/3: Ingesting all documents...")
    init_tables()
    try:
        report = ingest_directory(target)
    except Exception as exc:
        click.echo(f"Ingestion failed: {exc}", err=True)
        sys.exit(1)

    summary = report.summary()
    click.echo("")
    click.echo("=" * 56)
    click.echo("  REINDEX COMPLETE")
    click.echo("=" * 56)
    click.echo(f"Files seen     : {summary['files_seen']}")
    click.echo(f"  Added        : {summary['files_added']}")
    click.echo(f"  Updated      : {summary['files_updated']}")
    click.echo(f"  Skipped      : {summary['files_skipped']}")
    click.echo(f"  Failed       : {summary['files_failed']}")
    click.echo(f"Chunks indexed : {summary['chunks_added']}")
    click.echo(f"Tables         : {summary['tables_extracted']}")
    if summary["errors"]:
        click.echo("\nErrors:")
        for err in summary["errors"]:
            click.echo(f"  - {err}", err=True)
        sys.exit(1)

    click.echo("\nRestart the API server if it was running, then ask your questions.")


if __name__ == "__main__":
    main()
