"""
app/documents/table_extractor.py — Convert PDF table candidates into Markdown text.

Primary engine: pdfplumber tables (already extracted during PDF parsing).
Optional: Camelot, Tabula.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TableChunk:
    """A single extracted table converted to Markdown text."""

    page_number: int
    table_index: int
    markdown: str
    columns: list[str]
    row_count: int
    engine: str
    confidence: float | None = None


def tables_from_pdfplumber_page(
    tables_raw: list[list[list[str | None]]],
    page_number: int,
    section_title: str = "",
) -> list[TableChunk]:
    """Convert raw pdfplumber table data to TableChunk objects."""
    results: list[TableChunk] = []
    for idx, table in enumerate(tables_raw):
        if not table or not any(table):
            continue
        md = _table_to_markdown(table, section_title=section_title, page_number=page_number)
        header_row = table[0] if table else []
        columns = [str(c) if c is not None else "" for c in header_row]
        row_count = max(0, len(table) - 1)  # exclude header
        results.append(
            TableChunk(
                page_number=page_number,
                table_index=idx,
                markdown=md,
                columns=columns,
                row_count=row_count,
                engine="pdfplumber",
            )
        )
    return results


def tables_from_camelot(
    path: str | Path,
    page_number: int | None = None,
) -> list[TableChunk]:
    """Extract tables using Camelot (optional)."""
    try:
        import camelot  # type: ignore[import]
    except ImportError:
        logger.debug("camelot not installed; skipping Camelot table extraction.")
        return []

    try:
        pages_arg = str(page_number) if page_number else "all"
        tables = camelot.read_pdf(str(path), pages=pages_arg, flavor="lattice")
        results: list[TableChunk] = []
        for idx, t in enumerate(tables):
            df = t.df
            md = df.to_markdown(index=False)
            columns = list(df.columns)
            results.append(
                TableChunk(
                    page_number=t.page,
                    table_index=idx,
                    markdown=md or "",
                    columns=columns,
                    row_count=len(df),
                    engine="camelot",
                    confidence=t.accuracy / 100.0 if t.accuracy else None,
                )
            )
        return results
    except Exception as exc:
        logger.warning("Camelot extraction failed: %s", exc)
        return []


def _table_to_markdown(
    table: list[list[Any]],
    section_title: str = "",
    page_number: int | None = None,
) -> str:
    """Convert a raw 2D table list to a Markdown string."""
    if not table:
        return ""

    lines: list[str] = []
    if section_title:
        lines.append(f"**Table from: {section_title}**")
    if page_number:
        lines.append(f"*(Page {page_number})*")

    # Normalise cells
    def cell(v: Any) -> str:
        return str(v).strip().replace("\n", " ") if v is not None else ""

    rows = [[cell(c) for c in row] for row in table]

    if not rows:
        return "\n".join(lines)

    # Determine column count from the widest row
    col_count = max(len(r) for r in rows)
    # Pad short rows
    rows = [r + [""] * (col_count - len(r)) for r in rows]

    header = rows[0]
    separator = ["---"] * col_count
    body = rows[1:]

    def md_row(r: list[str]) -> str:
        return "| " + " | ".join(r) + " |"

    lines.append(md_row(header))
    lines.append(md_row(separator))
    for row in body:
        lines.append(md_row(row))

    return "\n".join(lines)
