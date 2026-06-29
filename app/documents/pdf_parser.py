"""
app/documents/pdf_parser.py — PDF text extraction with pdfplumber (primary) and pypdf (fallback).

Returns a list of PageResult objects — one per PDF page — with raw text,
layout hints, and extraction metadata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    """Extracted content for one PDF page."""

    page_number: int  # 1-indexed
    text: str
    width: float | None = None
    height: float | None = None
    extraction_method: str = "pdfplumber"
    char_count: int = 0
    word_count: int = 0
    needs_ocr: bool = False
    tables_raw: list[Any] = field(default_factory=list)  # raw pdfplumber table objects
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)
        self.word_count = len(self.text.split())


def extract_pdf_pdfplumber(
    path: str | Path,
    ocr_min_chars: int = 40,
    extract_tables: bool = True,
) -> list[PageResult]:
    """Extract pages from a PDF using pdfplumber."""
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError:
        logger.warning("pdfplumber not installed; falling back to pypdf.")
        return extract_pdf_pypdf(path, ocr_min_chars=ocr_min_chars)

    results: list[PageResult] = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                tables_raw = []
                if extract_tables:
                    try:
                        tables_raw = page.extract_tables() or []
                    except Exception as exc:
                        logger.debug("Table extraction failed on page %d: %s", i, exc)

                pr = PageResult(
                    page_number=i,
                    text=text,
                    width=float(page.width) if page.width else None,
                    height=float(page.height) if page.height else None,
                    extraction_method="pdfplumber",
                    tables_raw=tables_raw,
                )
                pr.needs_ocr = pr.char_count < ocr_min_chars
                results.append(pr)
    except Exception as exc:
        logger.error("pdfplumber failed on %s: %s — trying pypdf fallback.", path, exc)
        return extract_pdf_pypdf(path, ocr_min_chars=ocr_min_chars)

    return results


def extract_pdf_pypdf(
    path: str | Path,
    ocr_min_chars: int = 40,
) -> list[PageResult]:
    """Extract pages from a PDF using pypdf (fallback)."""
    try:
        from pypdf import PdfReader  # type: ignore[import]
    except ImportError:
        logger.error("pypdf not installed; cannot extract PDF %s.", path)
        return []

    results: list[PageResult] = []
    try:
        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pr = PageResult(
                page_number=i,
                text=text,
                extraction_method="pypdf",
            )
            pr.needs_ocr = pr.char_count < ocr_min_chars
            results.append(pr)
    except Exception as exc:
        logger.error("pypdf also failed on %s: %s", path, exc)

    return results


def extract_pdf(
    path: str | Path,
    parser: str = "pdfplumber",
    fallback_parser: str = "pypdf",
    ocr_min_chars: int = 40,
    extract_tables: bool = True,
) -> list[PageResult]:
    """Route to the configured parser with automatic fallback."""
    if parser == "pdfplumber":
        pages = extract_pdf_pdfplumber(
            path, ocr_min_chars=ocr_min_chars, extract_tables=extract_tables
        )
    else:
        pages = extract_pdf_pypdf(path, ocr_min_chars=ocr_min_chars)

    if not pages:
        logger.warning(
            "Primary parser '%s' returned no pages for %s; trying fallback '%s'.",
            parser,
            path,
            fallback_parser,
        )
        if fallback_parser == "pdfplumber" and parser != "pdfplumber":
            pages = extract_pdf_pdfplumber(
                path, ocr_min_chars=ocr_min_chars, extract_tables=extract_tables
            )
        else:
            pages = extract_pdf_pypdf(path, ocr_min_chars=ocr_min_chars)

    return pages
