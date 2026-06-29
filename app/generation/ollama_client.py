"""
app/generation/ollama_client.py — Thin async HTTP wrapper around the Ollama API.

Supports non-streaming and streaming chat completions.
Uses a persistent httpx client for connection pooling (faster repeated calls).
Automatically uses FALLBACK_LLM_MODEL if the primary model is unavailable.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import LLMUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a shared async HTTP client with connection pooling."""
    global _client
    if _client is None or _client.is_closed:
        settings = get_settings()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


def _build_options(temperature: float, max_tokens: int, **kwargs: Any) -> dict[str, Any]:
    settings = get_settings()
    options: dict[str, Any] = {
        "temperature": temperature,
        "num_predict": max_tokens,
        "num_ctx": 4096,  # Fit full retrieval contexts
    }
    options.update(kwargs)
    return options


def _build_payload(
    messages: list[dict[str, str]],
    model: str,
    *,
    stream: bool,
    temperature: float,
    max_tokens: int,
    **kwargs: Any,
) -> dict[str, Any]:
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "keep_alive": "30m",
        "options": _build_options(temperature, max_tokens, **kwargs),
    }
    if settings.llm_disable_thinking:
        payload["think"] = False
    return payload


async def chat_complete(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    **kwargs: Any,
) -> str:
    """Send a chat request to Ollama and return the full response text."""
    settings = get_settings()
    model = model or settings.llm_model
    url = f"{settings.ollama_base_url}/api/chat"

    payload = _build_payload(
        messages,
        model,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )

    client = _get_client()
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message", {})
        thinking = msg.get("thinking") or ""
        if thinking:
            logger.debug("Discarded LLM thinking (%d chars)", len(thinking))
        return msg.get("content", "") or ""
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404 and model != settings.fallback_llm_model:
            logger.warning(
                "Model '%s' not found; retrying with fallback '%s'.",
                model,
                settings.fallback_llm_model,
            )
            return await chat_complete(
                messages,
                model=settings.fallback_llm_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        logger.error("Ollama HTTP error: %s", exc)
        raise LLMUnavailableError(model) from exc
    except Exception as exc:
        logger.error("Ollama request failed: %s", exc)
        raise LLMUnavailableError(model) from exc


async def chat_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """Stream tokens from Ollama chat API as an async generator of text chunks."""
    settings = get_settings()
    model = model or settings.llm_model
    url = f"{settings.ollama_base_url}/api/chat"

    payload = _build_payload(
        messages,
        model,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    client = _get_client()
    try:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    # Never stream thinking tokens to the client
                    token = msg.get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        logger.error("Streaming failed: %s", exc)
        raise LLMUnavailableError(model) from exc


async def warmup_llm() -> None:
    """Pre-load the LLM into Ollama memory to avoid cold-start latency."""
    settings = get_settings()
    try:
        await chat_complete(
            [{"role": "user", "content": "hi"}],
            model=settings.llm_model,
            temperature=0.0,
            max_tokens=1,
        )
        logger.info("LLM model '%s' warmed up.", settings.llm_model)
    except Exception as exc:
        logger.warning("LLM warmup for '%s' failed: %s", settings.llm_model, exc)


async def check_model_available(model: str | None = None) -> bool:
    """Check if a model is available in Ollama."""
    settings = get_settings()
    model = model or settings.llm_model
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        client = _get_client()
        resp = await client.get(url, timeout=5.0)
        data = resp.json()
        names = [m.get("name", "") for m in data.get("models", [])]
        return any(model in n for n in names)
    except Exception:
        return False


async def close_client() -> None:
    """Close the shared HTTP client (called on shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
