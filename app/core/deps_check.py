"""Verify required Python packages before indexing or serving."""

from __future__ import annotations

REQUIRED = (
    ("sentence_transformers", "sentence-transformers"),
    ("chromadb", "chromadb"),
    ("rank_bm25", "rank-bm25"),
    ("pdfplumber", "pdfplumber"),
    ("pypdf", "pypdf"),
    ("diskcache", "diskcache"),
)


def check_dependencies() -> list[str]:
    """Return pip package names that are missing."""
    missing: list[str] = []
    for module, package in REQUIRED:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    return missing


def ensure_dependencies() -> None:
    missing = check_dependencies()
    if missing:
        packages = " ".join(missing)
        raise SystemExit(
            "Missing Python packages: "
            + ", ".join(missing)
            + "\n\nActivate the venv and install dependencies:\n"
            "  .venv\\Scripts\\activate\n"
            "  pip install -e .\n\n"
            f"Or install missing packages directly:\n"
            f"  pip install {packages}"
        )
