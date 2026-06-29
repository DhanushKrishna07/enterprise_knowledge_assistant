"""
app/indexing/bm25_store.py — BM25 keyword index using rank-bm25.

The BM25 index is rebuilt from all chunk texts on startup (or after ingestion).
It is serialised to disk with pickle for fast restarts.
"""

from __future__ import annotations

import pickle
import string
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would could should may might "
    "must shall can need dare ought used to of in on at by for with about against between into through "
    "during before after above below to from up down out off over under again further then once here there "
    "when where why how all both each few more most other some such no nor not only own same so than too "
    "very just".split()
)


def _tokenize(text: str) -> list[str]:
    """Simple, deterministic tokenizer: lowercase, remove punctuation, filter stopwords."""
    text = text.lower()
    text = text.translate(str.maketrans(string.punctuation, " " * len(string.punctuation)))
    tokens = [t for t in text.split() if t.isalnum() and t not in _STOPWORDS and len(t) > 1]
    return tokens


class BM25Store:
    """In-memory BM25 index with disk serialization."""

    def __init__(self) -> None:
        self._corpus_ids: list[str] = []  # parallel: chunk IDs
        self._corpus_tokens: list[list[str]] = []
        self._corpus_meta: list[dict[str, Any]] = []
        self._bm25: Any = None
        self._dirty: bool = False

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """
        Add chunks to the BM25 corpus.
        Each chunk dict must have 'chunk_id', 'text', and any metadata fields.
        """
        for chunk in chunks:
            cid = chunk["chunk_id"]
            text = chunk.get("text", "")
            if cid not in self._corpus_ids:
                self._corpus_ids.append(cid)
                self._corpus_tokens.append(_tokenize(text))
                self._corpus_meta.append({k: v for k, v in chunk.items() if k != "text"})
        self._bm25 = None  # invalidate
        self._dirty = True

    def remove_by_document_id(self, document_id: str) -> int:
        """Remove all chunks for a given document_id. Returns count removed."""
        keep_ids, keep_tokens, keep_meta = [], [], []
        removed = 0
        for cid, tokens, meta in zip(self._corpus_ids, self._corpus_tokens, self._corpus_meta):
            if meta.get("document_id") == document_id:
                removed += 1
            else:
                keep_ids.append(cid)
                keep_tokens.append(tokens)
                keep_meta.append(meta)
        self._corpus_ids = keep_ids
        self._corpus_tokens = keep_tokens
        self._corpus_meta = keep_meta
        self._bm25 = None
        self._dirty = True
        return removed

    def _build(self) -> None:
        if self._bm25 is not None:
            return
        if not self._corpus_tokens:
            self._bm25 = None
            return
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import]

            self._bm25 = BM25Okapi(self._corpus_tokens)
        except ImportError:
            logger.error("rank-bm25 not installed; keyword search unavailable.")
            self._bm25 = None

    def query(
        self,
        query: str,
        n_results: int = 30,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return top-n BM25 results with scores, optionally filtered by metadata."""
        self._build()
        if self._bm25 is None or not self._corpus_ids:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        results = []
        for i, score in enumerate(scores):
            if score <= 0:
                continue
            meta = self._corpus_meta[i]
            # Apply optional metadata filters
            if where and not _matches_filter(meta, where):
                continue
            results.append(
                {
                    "chunk_id": self._corpus_ids[i],
                    "bm25_score": float(score),
                    **meta,
                }
            )

        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:n_results]

    def save(self, path: str | None = None) -> None:
        save_path = path or _default_path()
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(
                {
                    "ids": self._corpus_ids,
                    "tokens": self._corpus_tokens,
                    "meta": self._corpus_meta,
                },
                f,
            )
        self._dirty = False
        logger.info("BM25 index saved (%d chunks).", len(self._corpus_ids))

    def load(self, path: str | None = None) -> bool:
        load_path = path or _default_path()
        if not Path(load_path).exists():
            return False
        try:
            with open(load_path, "rb") as f:
                data = pickle.load(f)
            self._corpus_ids = data["ids"]
            self._corpus_tokens = data["tokens"]
            self._corpus_meta = data["meta"]
            self._bm25 = None  # will rebuild on next query
            logger.info("BM25 index loaded (%d chunks).", len(self._corpus_ids))
            return True
        except Exception as exc:
            logger.error("Failed to load BM25 index: %s", exc)
            return False

    @property
    def chunk_count(self) -> int:
        return len(self._corpus_ids)


# ── Module-level singleton ────────────────────────────────────────────────────

_store_instance: BM25Store | None = None


def get_bm25_store() -> BM25Store:
    global _store_instance
    if _store_instance is None:
        _store_instance = BM25Store()
        _store_instance.load()  # loads from disk if available
    return _store_instance


def reset_bm25_store() -> None:
    """Drop in-memory BM25 singleton (used after deleting the pickle file)."""
    global _store_instance
    _store_instance = None


def _default_path() -> str:
    settings = get_settings()
    return str(Path(settings.chroma_path).parent / "bm25_index.pkl")


# ── Filter helper ─────────────────────────────────────────────────────────────


def _matches_filter(meta: dict[str, Any], where: dict[str, Any]) -> bool:
    """Simple metadata filter: equality checks on allowed_roles and department."""
    for key, condition in where.items():
        val = meta.get(key, "")
        if isinstance(condition, dict):
            op, operand = next(iter(condition.items()))
            if op == "$eq" and str(val) != str(operand):
                return False
            elif op == "$contains" and str(operand) not in str(val):
                return False
            elif op == "$in":
                if isinstance(operand, (list, tuple, set)):
                    if val not in operand:
                        return False
                elif val != operand:
                    return False
        elif str(val) != str(condition):
            return False
    return True
