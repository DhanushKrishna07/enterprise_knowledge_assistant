"""Dedicated thread pools so document sync never blocks retrieval."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

T = TypeVar("T")

_retrieval_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="retrieval")


async def run_retrieval(fn: Callable[[], T]) -> T:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_retrieval_executor, fn)


async def run_retrieval_fn(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_retrieval_executor, lambda: fn(*args, **kwargs))
