"""
app/documents/hashing.py — Content hashing utilities for deduplication.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_checksum(path: str | Path, algorithm: str = "sha256") -> str:
    """Return hex digest of a file's contents."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def text_checksum(text: str, algorithm: str = "sha256") -> str:
    """Return hex digest of a UTF-8 string."""
    return hashlib.new(algorithm, text.encode("utf-8")).hexdigest()


def document_id(filename: str, content_checksum: str) -> str:
    """Stable document ID derived from filename + content hash."""
    raw = f"{filename}::{content_checksum}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
