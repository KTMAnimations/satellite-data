from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Callable, ParamSpec, TypeVar

from fastapi import HTTPException, Request

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


async def gee_to_thread_or_499(
    request: Request,
    func: Callable[P, R],
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """
    Like `gee_to_thread`, but aborts quickly if the client disconnects.

    This is important for UI flows where users rapidly switch metrics/dates: we don't
    want to queue expensive Earth Engine work for requests that are no longer needed.
    """
    sem = get_gee_semaphore()
    poll_seconds = 0.25

    while True:
        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="Client disconnected")
        try:
            await asyncio.wait_for(sem.acquire(), timeout=poll_seconds)
            break
        except asyncio.TimeoutError:
            continue

    try:
        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="Client disconnected")
        return await asyncio.to_thread(func, *args, **kwargs)
    finally:
        sem.release()
