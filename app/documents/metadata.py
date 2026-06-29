"""
app/documents/metadata.py — Document and chunk metadata helpers.

Metadata is stored alongside each chunk in Chroma and SQLite.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DocumentMeta:
    """Metadata for a whole document (before chunking)."""

    document_id: str
    filename: str
    file_type: str  # pdf, docx, txt, md, csv
    checksum: str
    department: str = "general"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    policy_version: str = ""
    upload_date: str = ""  # ISO date string, e.g. "2026-01-15"
    access_roles: list[str] = field(default_factory=lambda: ["employee"])
    created_at: str = field(default_factory=lambda: _now())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Chroma metadata values must be str/int/float/bool — serialize lists
        d["tags"] = ",".join(self.tags)
        d["access_roles"] = ",".join(self.access_roles)
        return d


@dataclass
class ChunkMeta:
    """Metadata for a single text/table chunk."""

    chunk_id: str
    document_id: str
    filename: str
    file_type: str
    chunk_index: int
    page_number: int | None  # None for non-page-structured formats
    page_start: int | None = None
    page_end: int | None = None
    section_title: str = ""
    content_type: str = "text"  # text | table | ocr_text
    extraction_method: str = (
        "text"  # pdfplumber | pypdf | tesseract_ocr | easyocr | python-docx | plaintext | csv
    )
    content_hash: str = ""
    department: str = "general"
    author: str = ""
    tags: str = ""  # comma-separated string for Chroma compat
    policy_version: str = ""
    upload_date: str = ""
    access_roles: str = "employee"  # comma-separated string
    # Table-specific extras
    table_index: int | None = None
    columns: str = ""  # comma-separated column names
    row_count: int | None = None
    table_confidence: float | None = None
    table_engine: str = ""
    ingested_at: str = field(default_factory=lambda: _now())

    def to_chroma_metadata(self) -> dict[str, Any]:
        """Return a flat dict of Chroma-compatible scalar metadata."""
        d = asdict(self)
        # Replace None with empty string (Chroma does not accept None)
        return {k: ("" if v is None else v) for k, v in d.items()}


def build_chunk_meta(
    *,
    chunk_id: str,
    doc_meta: DocumentMeta,
    chunk_index: int,
    content_hash: str,
    page_number: int | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    section_title: str = "",
    content_type: str = "text",
    extraction_method: str = "text",
    table_index: int | None = None,
    columns: list[str] | None = None,
    row_count: int | None = None,
    table_confidence: float | None = None,
    table_engine: str = "",
) -> ChunkMeta:
    return ChunkMeta(
        chunk_id=chunk_id,
        document_id=doc_meta.document_id,
        filename=doc_meta.filename,
        file_type=doc_meta.file_type,
        chunk_index=chunk_index,
        page_number=page_number,
        page_start=page_start,
        page_end=page_end,
        section_title=section_title,
        content_type=content_type,
        extraction_method=extraction_method,
        content_hash=content_hash,
        department=doc_meta.department,
        author=doc_meta.author,
        tags=",".join(doc_meta.tags),
        policy_version=doc_meta.policy_version,
        upload_date=doc_meta.upload_date,
        access_roles=",".join(doc_meta.access_roles),
        table_index=table_index,
        columns=",".join(columns) if columns else "",
        row_count=row_count,
        table_confidence=table_confidence,
        table_engine=table_engine,
    )


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
