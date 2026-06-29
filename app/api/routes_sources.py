"""
app/api/routes_sources.py — Source preview endpoint for chunk details.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.api.schemas import SourcePreviewResponse
from app.indexing.chroma_store import get_chunk_by_id

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/{chunk_id}", response_model=SourcePreviewResponse)
async def get_source(
    chunk_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """Return full chunk text and metadata for source preview."""
    chunk = get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Source chunk not found.")

    if current_user.get("role") != "admin":
        roles = [r.strip() for r in chunk.get("access_roles", "employee").split(",")]
        if current_user.get("role", "employee") not in roles:
            raise HTTPException(status_code=403, detail="Access denied to this source.")

    return SourcePreviewResponse(
        chunk_id=chunk_id,
        document=chunk.get("filename", "Unknown"),
        page=chunk.get("page_number") or None,
        text=chunk.get("text", ""),
        content_type=chunk.get("content_type", "text"),
        extraction_method=chunk.get("extraction_method", ""),
        section_title=chunk.get("section_title", ""),
        department=chunk.get("department", ""),
        document_id=chunk.get("document_id", ""),
        tags=chunk.get("tags", ""),
        policy_version=chunk.get("policy_version", ""),
        uploaded_at=chunk.get("uploaded_at", chunk.get("ingested_at", "")),
    )
