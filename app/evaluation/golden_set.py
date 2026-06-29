"""
app/evaluation/golden_set.py — Parser and loader for YAML-formatted Golden QA sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class GoldenQAItem:
    id: str
    question: str
    expected_answer_facts: list[str]
    expected_sources: list[str]  # list of expected document names
    answerable: bool
    tags: list[str]


def load_golden_set(filepath: str | Path) -> list[GoldenQAItem]:
    """Load and parse Golden QA items from a YAML file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Golden QA dataset not found at: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    items = []
    for item in data:
        expected_sources = []
        for src in item.get("expected_sources", []):
            if isinstance(src, dict):
                expected_sources.append(src.get("document", ""))
            elif isinstance(src, str):
                expected_sources.append(src)

        items.append(
            GoldenQAItem(
                id=item["id"],
                question=item["question"],
                expected_answer_facts=item.get("expected_answer_facts") or [],
                expected_sources=expected_sources,
                answerable=item.get("answerable", True),
                tags=item.get("tags") or [],
            )
        )
    return items
