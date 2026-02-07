from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Callable, ParamSpec, TypeVar

from app.settings import get_settings

P = ParamSpec("P")
R = TypeVar("R")


@lru_cache
def get_gee_semaphore() -> asyncio.Semaphore:
    """
    Global, in-process concurrency limiter for Earth Engine work.

    Earth Engine calls are blocking (and run via `asyncio.to_thread`), so without a
    shared limiter fast pans/zooms can saturate the threadpool and amplify EE
    quota/latency issues.
    """
    settings = get_settings()
    return asyncio.Semaphore(settings.gee_max_concurrent_requests)


async def gee_to_thread(func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    sem = get_gee_semaphore()
    async with sem:
        return await asyncio.to_thread(func, *args, **kwargs)

