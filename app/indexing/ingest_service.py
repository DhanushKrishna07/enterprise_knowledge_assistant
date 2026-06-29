"""
app/indexing/ingest_service.py — Orchestrate the full ingestion pipeline.

Flow:
  load_document → chunk → embed → upsert Chroma → update BM25 → update SQLite
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.documents.chunker import TextChunk, chunk_pages
from app.documents.hashing import text_checksum
from app.documents.jobs import (
    IngestionJob,
    JobStatus,
    create_run,
    init_tables,
    update_run,
    upsert_job,
)
from app.documents.loaders import LoadedDocument, load_document
from app.documents.metadata import build_chunk_meta
from app.indexing.bm25_store import get_bm25_store
from app.indexing.chroma_store import delete_by_document_id, upsert_chunks
from app.indexing.embeddings import embed_texts

logger = get_logger(__name__)


@dataclass
class IngestionReport:
    run_id: str
    files_seen: int = 0
    files_added: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    chunks_added: int = 0
    ocr_pages: int = 0
    tables_extracted: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "files_seen": self.files_seen,
            "files_added": self.files_added,
            "files_updated": self.files_updated,
            "files_skipped": self.files_skipped,
            "files_failed": self.files_failed,
            "chunks_added": self.chunks_added,
            "ocr_pages": self.ocr_pages,
            "tables_extracted": self.tables_extracted,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def ingest_directory(directory: str | Path, run_id: str | None = None) -> IngestionReport:
    """Ingest all supported documents in a directory (non-recursive)."""
    settings = get_settings()
    init_tables()
    run_id = run_id or str(uuid.uuid4())
    create_run(run_id)
    report = IngestionReport(run_id=run_id)

    directory = Path(directory)
    supported = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}
    files = [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in supported]
    report.files_seen = len(files)

    for file_path in files:
        job_id = str(uuid.uuid4())
        job = IngestionJob(id=job_id, run_id=run_id, filename=file_path.name)
        upsert_job(job)

        try:
            result = ingest_file(file_path, job=job)
            report.files_added += result.get("added", 0)
            report.files_updated += result.get("updated", 0)
            report.files_skipped += result.get("skipped", 0)
            report.chunks_added += result.get("chunks_added", 0)
            report.ocr_pages += result.get("ocr_pages", 0)
            report.tables_extracted += result.get("tables_extracted", 0)
            report.warnings.extend(result.get("warnings", []))
        except Exception as exc:
            report.files_failed += 1
            report.errors.append(f"{file_path.name}: {exc}")
            logger.error("Ingestion failed for %s: %s", file_path.name, exc)
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = _now()
            upsert_job(job)

    update_run(
        run_id,
        status="completed",
        files_seen=report.files_seen,
        files_added=report.files_added,
        files_updated=report.files_updated,
        files_skipped=report.files_skipped,
        files_failed=report.files_failed,
        chunks_added=report.chunks_added,
        ocr_pages=report.ocr_pages,
        tables_extracted=report.tables_extracted,
        finished_at=_now(),
    )

    # Save BM25 index after full run
    get_bm25_store().save()

    return report


def ingest_file(
    path: str | Path,
    job: IngestionJob | None = None,
) -> dict[str, Any]:
    """Ingest a single file. Returns a summary dict."""
    settings = get_settings()
    path = Path(path)

    _update_job(job, JobStatus.EXTRACTING, "extracting", 0.1)

    from app.documents.hashing import document_id, file_checksum

    checksum = file_checksum(path)
    doc_id = document_id(path.name, checksum)
    existing_checksum = _get_indexed_checksum(doc_id)
    if existing_checksum == checksum:
        _update_job(job, JobStatus.SKIPPED, "unchanged", 1.0)
        logger.info("Skipping unchanged document: %s", path.name)
        return {"skipped": 1}

    loaded: LoadedDocument | None = load_document(path)
    if loaded is None or not loaded.pages:
        _update_job(job, JobStatus.FAILED, "load_failed", 1.0, error="No content extracted.")
        return {"skipped": 1, "warnings": [f"{path.name}: no content extracted."]}

    doc_meta = loaded.doc_meta

    # If document existed before, remove old chunks
    action = "added"
    if existing_checksum is not None:
        delete_by_document_id(doc_meta.document_id)
        get_bm25_store().remove_by_document_id(doc_meta.document_id)
        action = "updated"

    _update_job(job, JobStatus.CHUNKING, "chunking", 0.3)

    # Chunk text pages
    page_pairs = [(pn if pn else 1, txt) for pn, txt in loaded.pages]
    text_chunks = chunk_pages(
        page_pairs,
        target_tokens=settings.top_k_context,  # reuse setting; actually from config
        # Use hard-coded defaults aligned with plan
    )
    # Re-chunk with correct settings
    text_chunks = _chunk_pages_with_settings(page_pairs)

    all_ids: list[str] = []
    all_texts: list[str] = []
    all_metadatas: list[dict] = []
    all_hashes: list[str] = []
    bm25_chunks: list[dict] = []

    for tc in text_chunks:
        c_hash = text_checksum(tc.text)
        c_id = _chunk_id(doc_meta.document_id, tc.chunk_index, c_hash)
        method = loaded.extraction_methods[0] if loaded.extraction_methods else "plaintext"
        cm = build_chunk_meta(
            chunk_id=c_id,
            doc_meta=doc_meta,
            chunk_index=tc.chunk_index,
            content_hash=c_hash,
            page_number=tc.page_number,
            page_start=tc.page_start,
            page_end=tc.page_end,
            section_title=tc.section_title,
            content_type="text",
            extraction_method=method,
        )
        meta = cm.to_chroma_metadata()
        all_ids.append(c_id)
        all_texts.append(tc.text)
        all_metadatas.append(meta)
        all_hashes.append(c_hash)
        bm25_chunks.append({"chunk_id": c_id, "text": tc.text, **meta})

    # Table chunks
    offset = len(text_chunks)
    for t_idx, tc in enumerate(loaded.table_chunks):
        c_hash = text_checksum(tc.markdown)
        c_id = _chunk_id(doc_meta.document_id, offset + t_idx, c_hash)
        cm = build_chunk_meta(
            chunk_id=c_id,
            doc_meta=doc_meta,
            chunk_index=offset + t_idx,
            content_hash=c_hash,
            page_number=tc.page_number,
            content_type="table",
            extraction_method=tc.engine,
            table_index=tc.table_index,
            columns=tc.columns,
            row_count=tc.row_count,
            table_confidence=tc.confidence,
            table_engine=tc.engine,
        )
        meta = cm.to_chroma_metadata()
        all_ids.append(c_id)
        all_texts.append(tc.markdown)
        all_metadatas.append(meta)
        all_hashes.append(c_hash)
        bm25_chunks.append({"chunk_id": c_id, "text": tc.markdown, **meta})

    _update_job(job, JobStatus.EMBEDDING, "embedding", 0.55)

    embeddings = embed_texts(all_texts, content_hashes=all_hashes)

    _update_job(job, JobStatus.INDEXING, "indexing", 0.8)

    upsert_chunks(all_ids, all_texts, embeddings, all_metadatas)
    get_bm25_store().add_chunks(bm25_chunks)

    # Record checksum for future dedup
    _store_indexed_checksum(doc_meta.document_id, doc_meta.checksum)

    chunks_added = len(all_ids)
    tables_extracted = len(loaded.table_chunks)

    if job:
        job.status = JobStatus.COMPLETED
        job.stage = "completed"
        job.progress = 1.0
        job.chunks_added = chunks_added
        job.ocr_pages = loaded.ocr_page_count
        job.tables_extracted = tables_extracted
        job.finished_at = _now()
        upsert_job(job)

    logger.info(
        "Ingested %s: %s chunks, %d OCR pages, %d tables.",
        path.name,
        chunks_added,
        loaded.ocr_page_count,
        tables_extracted,
    )

    return {
        action: 1,
        "chunks_added": chunks_added,
        "ocr_pages": loaded.ocr_page_count,
        "tables_extracted": tables_extracted,
        "warnings": loaded.warnings,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _chunk_pages_with_settings(page_pairs: list[tuple[int, str]]) -> list[TextChunk]:
    from app.documents.chunker import chunk_pages

    return chunk_pages(
        page_pairs,
        target_tokens=700,
        max_tokens=1_000,
        overlap_tokens=120,
    )


def _chunk_id(document_id: str, chunk_index: int, content_hash: str) -> str:
    raw = f"{document_id}::{chunk_index}::{content_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ── Simple SQLite checksum store (reuses jobs DB) ─────────────────────────────


def _get_indexed_checksum(document_id: str) -> str | None:
    from app.documents.jobs import _connect

    try:
        with _connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS indexed_documents "
                "(document_id TEXT PRIMARY KEY, checksum TEXT, indexed_at TEXT)"
            )
            row = conn.execute(
                "SELECT checksum FROM indexed_documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def _store_indexed_checksum(document_id: str, checksum: str) -> None:
    from app.documents.jobs import _connect

    try:
        with _connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS indexed_documents "
                "(document_id TEXT PRIMARY KEY, checksum TEXT, indexed_at TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO indexed_documents (document_id, checksum, indexed_at) VALUES (?, ?, ?)",
                (document_id, checksum, _now()),
            )
    except Exception as exc:
        logger.error("Failed to store checksum: %s", exc)


def _update_job(
    job: IngestionJob | None, status: str, stage: str, progress: float, error: str = ""
) -> None:
    if job is None:
        return
    job.status = status
    job.stage = stage
    job.progress = progress
    if error:
        job.error = error
    upsert_job(job)


def _now() -> str:
    import datetime

    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def delete_document(document_id: str) -> dict[str, Any]:
    """Remove a document and all its chunks from Chroma and BM25 indexes, and delete it from disk."""
    settings = get_settings()

    # Try to find filename from Chroma collection before deleting
    filename = None
    try:
        from app.indexing.chroma_store import get_collection

        col = get_collection()
        res = col.get(where={"document_id": {"$eq": document_id}}, limit=1, include=["metadatas"])
        if res.get("metadatas"):
            filename = res["metadatas"][0].get("filename")
    except Exception as exc:
        logger.warning("Failed to lookup filename for document deletion: %s", exc)

    # Delete physical file from data/documents
    file_deleted = False
    if filename:
        file_path = Path(settings.documents_path) / filename
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info("Deleted physical file from disk: %s", file_path)
                file_deleted = True
        except Exception as exc:
            logger.error("Failed to delete physical file %s: %s", file_path, exc)

    chroma_deleted = delete_by_document_id(document_id)
    bm25_deleted = get_bm25_store().remove_by_document_id(document_id)
    get_bm25_store().save()

    try:
        init_tables()
        import sqlite3

        db = settings.sqlite_url.replace("sqlite:///", "")
        with sqlite3.connect(db) as conn:
            conn.execute("DELETE FROM indexed_documents WHERE document_id = ?", (document_id,))
    except Exception as exc:
        logger.warning("Failed to remove document checksum: %s", exc)

    return {
        "document_id": document_id,
        "chroma_chunks_deleted": chroma_deleted,
        "bm25_chunks_deleted": bm25_deleted,
        "file_deleted": file_deleted,
        "status": "deleted",
    }
