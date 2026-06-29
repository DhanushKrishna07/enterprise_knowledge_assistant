"""
app/api/schemas.py — Pydantic request and response models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Auth ──────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    department: str
    email: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    department: str


# ── Ask ───────────────────────────────────────────────────────────────────────


class AskFilters(BaseModel):
    department: str | None = None
    document_type: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    policy_version: str | None = None
    uploaded_after: str | None = None
    content_types: list[str] | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    top_k: int | None = Field(None, ge=1, le=20)
    filters: AskFilters | None = None
    include_debug: bool = False


class CitationResponse(BaseModel):
    citation_id: int
    document: str
    page: int | None
    chunk_id: str
    snippet: str
    score: float
    content_type: str = "text"
    extraction_method: str = ""
    section_title: str = ""


class SourcePreviewResponse(BaseModel):
    chunk_id: str
    document: str
    page: int | None
    text: str
    content_type: str = "text"
    extraction_method: str = ""
    section_title: str = ""
    department: str = ""
    document_id: str = ""
    tags: str = ""
    policy_version: str = ""
    uploaded_at: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[CitationResponse]
    confidence: float
    session_id: str | None
    rewritten_query: str
    answerability: str  # answered | partially_answered | not_found
    retrieval_trace: dict[str, Any] | None = None
    latencies: dict[str, float] | None = None
    prompt_version: str | None = None


# ── Ingest ────────────────────────────────────────────────────────────────────


class IngestJobResponse(BaseModel):
    job_id: str
    run_id: str
    filename: str
    status: str
    stage: str
    progress: float
    chunks_added: int
    ocr_pages: int
    tables_extracted: int
    error: str
    started_at: str
    finished_at: str


class IngestRunResponse(BaseModel):
    run_id: str
    status: str
    files_seen: int
    files_added: int
    files_updated: int
    files_skipped: int
    files_failed: int
    chunks_added: int
    ocr_pages: int
    tables_extracted: int
    started_at: str
    finished_at: str


# ── Feedback ──────────────────────────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    message_id: str | None = None
    session_id: str | None = None
    question: str
    answer: str
    rating: int = Field(..., ge=-1, le=1)  # 1=up, -1=down, 0=neutral
    category: str | None = None  # incorrect | missing_source | incomplete | slow | other
    comment: str | None = None


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class ReadyResponse(BaseModel):
    status: str
    components: dict[str, str]
