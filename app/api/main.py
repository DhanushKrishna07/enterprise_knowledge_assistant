"""
app/api/main.py — FastAPI application entry point.

Registers all routers, error handlers, startup events, and CORS middleware.
Serves the React frontend from frontend/dist when available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_admin import router as admin_router
from app.api.routes_ask import router as ask_router
from app.api.routes_auth import router as auth_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_sources import router as sources_router
from app.api.schemas import HealthResponse, ReadyResponse
from app.auth.service import init_user_table, seed_demo_users
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import get_logger, setup_logging
from app.documents.jobs import init_tables
from app.observability.trace import init_trace_table

logger = get_logger(__name__)

app = FastAPI(
    title="Enterprise Knowledge Assistant",
    description="RAG-powered enterprise knowledge assistant using free/local AI models.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(auth_router)
app.include_router(ask_router)
app.include_router(ingest_router)
app.include_router(feedback_router)
app.include_router(admin_router)
app.include_router(sources_router)


@app.on_event("startup")
async def startup() -> None:
    import asyncio

    setup_logging()
    settings = get_settings()
    logger.info(
        "Starting Enterprise Knowledge Assistant",
        extra={
            "llm_model": settings.llm_model,
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
            "pdf_parser": settings.pdf_parser,
            "ocr_engine": settings.ocr_engine if settings.enable_ocr else "disabled",
            "table_engine": settings.table_engine
            if settings.enable_table_extraction
            else "disabled",
        },
    )

    init_tables()
    init_user_table()
    init_trace_table()
    seed_demo_users()

    try:
        from app.core.ml_preload import preload_ml_stack

        preload_ml_stack()
    except Exception as exc:
        logger.error(
            "ML dependency preload failed: %s. Run: .venv\\Scripts\\pip install -e .",
            exc,
        )

    # Heavy work runs in background so /health responds immediately.
    asyncio.create_task(_background_startup(settings))


async def _background_startup(settings: Any) -> None:
    """Warm retrieval models in the background (no automatic document sync)."""
    from app.core.startup_state import mark_models_ready, mark_warming

    mark_warming()

    if settings.warmup_models_on_startup:
        try:
            from app.core.executors import run_retrieval_fn
            from app.indexing.bm25_store import get_bm25_store
            from app.indexing.embeddings import embed_query

            await run_retrieval_fn(embed_query, "warmup query")
            logger.info("Embedding model warmed up.")
            await run_retrieval_fn(get_bm25_store)
            logger.info("BM25 index warmed up.")
        except Exception as exc:
            logger.warning("Retrieval warmup failed: %s", exc)

    mark_models_ready()

    if settings.warmup_models_on_startup:
        try:
            from app.generation.ollama_client import warmup_llm

            await warmup_llm()
        except Exception as exc:
            logger.warning("LLM warmup failed: %s", exc)


@app.on_event("shutdown")
async def shutdown() -> None:
    from app.generation.ollama_client import close_client

    await close_client()


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadyResponse, tags=["health"])
async def ready() -> ReadyResponse:
    components: dict[str, str] = {}

    try:
        from app.indexing.chroma_store import collection_stats

        collection_stats()
        components["chroma"] = "ok"
    except Exception as exc:
        components["chroma"] = f"error: {exc}"

    try:
        from app.generation.ollama_client import check_model_available

        available = await check_model_available()
        components["ollama"] = "ok" if available else "model_not_found"
    except Exception as exc:
        components["ollama"] = f"error: {exc}"

    settings = get_settings()
    if settings.enable_ocr:
        try:
            import pytesseract  # noqa: F401

            components["ocr_tesseract"] = "available"
        except ImportError:
            components["ocr_tesseract"] = "missing"
    else:
        components["ocr_tesseract"] = "disabled"

    overall = (
        "ok"
        if all(v in ("ok", "available", "disabled", "model_not_found") for v in components.values())
        else "degraded"
    )
    return ReadyResponse(status=overall, components=components)


# ── React frontend (SPA) ──────────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_API_PATH_PREFIXES = (
    "docs",
    "redoc",
    "openapi.json",
    "health",
    "ready",
    "ask",
    "auth",
    "ingest",
    "feedback",
    "admin",
    "sources",
)

if _FRONTEND_DIST.exists():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve React SPA for non-API routes."""
        if any(full_path.startswith(p) for p in _API_PATH_PREFIXES):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not found")
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIST / "index.html")
