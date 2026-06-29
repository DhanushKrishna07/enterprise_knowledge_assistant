"""
app/core/config.py — Application settings loaded from environment / .env file.

All configuration lives here. Change behaviour by editing .env, not code.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ─────────────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"
    fallback_llm_model: str = "qwen3:1.7b"
    llm_timeout: int = 20
    llm_generation_timeout: int = 8
    llm_stream_timeout: int = 30
    llm_disable_thinking: bool = True  # disable Qwen3 chain-of-thought; saves 20-30s
    answer_max_tokens: int = 256
    answer_max_sentences: int = 2
    rewrite_max_tokens: int = 40
    skip_rewrite_heuristic: bool = True
    enable_quick_extraction: bool = True  # skip LLM when fact is directly in chunks

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_device: str = "cpu"

    # ── Re-ranker ─────────────────────────────────────────────────────────────
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_device: str = "cpu"

    # ── PDF parsing ───────────────────────────────────────────────────────────
    pdf_parser: Literal["pdfplumber", "pypdf"] = "pdfplumber"
    pdf_fallback_parser: Literal["pdfplumber", "pypdf"] = "pypdf"

    # ── OCR ───────────────────────────────────────────────────────────────────
    enable_ocr: bool = True
    ocr_engine: Literal["tesseract", "easyocr"] = "tesseract"
    ocr_min_text_chars_per_page: int = 40
    tesseract_cmd: str = ""

    # ── Table extraction ──────────────────────────────────────────────────────
    enable_table_extraction: bool = True
    table_engine: Literal["pdfplumber", "camelot", "tabula"] = "pdfplumber"

    # ── Paths ─────────────────────────────────────────────────────────────────
    chroma_path: str = "data/index/chroma"
    sqlite_url: str = "sqlite:///data/app.db"
    cache_path: str = "data/cache"
    documents_path: str = "data/documents"

    # ── Retrieval ─────────────────────────────────────────────────────────────
    top_k_semantic: int = 10
    top_k_keyword: int = 10
    top_k_rerank: int = 5
    top_k_context: int = 3
    warmup_models_on_startup: bool = True
    rrf_k: int = 60
    no_answer_threshold: float = 0.40

    # ── Caching ───────────────────────────────────────────────────────────────
    enable_response_cache: bool = True
    cache_disabled: bool = False
    embedding_cache_ttl: int = -1  # -1 = permanent
    retrieval_cache_ttl: int = 600
    response_cache_ttl: int = 1200

    # ── Auth ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-for-local-demo"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ── Logging ───────────────────────────────────────────────────────────────
    log_format: Literal["json", "text"] = "json"
    log_level: str = "INFO"
    redact_questions: bool = True

    # ── Index versioning ──────────────────────────────────────────────────────
    index_version: int = 1

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()

    @field_validator("reranker_model")
    @classmethod
    def _normalize_reranker_model(cls, v: str) -> str:
        v = v.strip()
        if not v or v.startswith("#"):
            return ""
        return v

    # ── Derived helpers ───────────────────────────────────────────────────────

    @property
    def chroma_collection_name(self) -> str:
        """One Chroma collection per embedding model so dimension changes never corrupt the index."""
        slug = self.embedding_model.replace("/", "_").replace("-", "_").replace(".", "_").lower()
        return f"enterprise_chunks_{slug}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
