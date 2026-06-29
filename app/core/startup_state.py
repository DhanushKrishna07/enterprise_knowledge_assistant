"""Startup readiness — avoid serving /ask before models are loaded."""

from __future__ import annotations

import asyncio
import threading

_models_ready = threading.Event()
_warming = False


def mark_warming() -> None:
    global _warming
    _warming = True
    _models_ready.clear()


def mark_models_ready() -> None:
    global _warming
    _warming = False
    _models_ready.set()


def models_ready() -> bool:
    return _models_ready.is_set()


def is_warming() -> bool:
    return _warming


async def wait_for_models(timeout: float = 90.0) -> bool:
    """Wait until embedding/BM25 warmup finished. Returns False on timeout."""
    if _models_ready.is_set():
        return True
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, lambda: _models_ready.wait(timeout=timeout))
    except Exception:
        return False
    return _models_ready.is_set()
