"""
app/api/routes_ingest.py — Document ingestion routes.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_current_user, require_admin
from app.api.schemas import IngestJobResponse
from app.core.config import get_settings
from app.documents.jobs import (
    IngestionJob,
    JobStatus,
    get_job,
    get_run,
    init_tables,
    list_jobs,
    upsert_job,
)
from app.indexing.ingest_service import delete_document, ingest_directory, ingest_file

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("")
async def ingest_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    """Upload and ingest a single document (admin only)."""
    settings = get_settings()
    init_tables()

    # Save upload to documents directory
    upload_dir = Path(settings.documents_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    contents = await file.read()
    dest.write_bytes(contents)

    run_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    job = IngestionJob(id=job_id, run_id=run_id, filename=file.filename)
    upsert_job(job)

    background_tasks.add_task(_run_ingest, dest, job)

    return {"run_id": run_id, "job_id": job_id, "filename": file.filename, "status": "queued"}


@router.post("/directory")
async def ingest_dir(
    background_tasks: BackgroundTasks,
    directory: str | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    """Ingest all documents in a directory (admin only)."""
    settings = get_settings()
    target = Path(directory or settings.documents_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {target}")

    run_id = str(uuid.uuid4())
    background_tasks.add_task(_run_ingest_directory, str(target), run_id)
    return {"run_id": run_id, "status": "queued", "directory": str(target)}


@router.delete("/documents/{document_id}")
async def delete_ingested_document(
    document_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Remove a document and all associated chunks from the index (admin only)."""
    result = delete_document(document_id)
    if result["chroma_chunks_deleted"] == 0 and result["bm25_chunks_deleted"] == 0:
        raise HTTPException(status_code=404, detail="Document not found in index.")
    return result


@router.get("/jobs/{job_id}", response_model=IngestJobResponse)
async def get_ingest_job(
    job_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return IngestJobResponse(
        job_id=job["id"],
        run_id=job.get("run_id", ""),
        filename=job.get("filename", ""),
        status=job.get("status", ""),
        stage=job.get("stage", ""),
        progress=job.get("progress", 0.0),
        chunks_added=job.get("chunks_added", 0),
        ocr_pages=job.get("ocr_pages", 0),
        tables_extracted=job.get("tables_extracted", 0),
        error=job.get("error", ""),
        started_at=job.get("started_at", ""),
        finished_at=job.get("finished_at", ""),
    )


@router.get("/runs/{run_id}")
async def get_ingest_run(
    run_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    jobs = list_jobs(run_id)
    return {"run": run, "jobs": jobs}


async def _run_ingest(path: Path, job: IngestionJob) -> None:
    try:
        ingest_file(path, job=job)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        upsert_job(job)


async def _run_ingest_directory(directory: str, run_id: str) -> None:
    from app.documents.jobs import create_run

    create_run(run_id)
    ingest_directory(directory, run_id=run_id)
