from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

import httpx


def request_with_retry(
    request_fn: Callable[[], httpx.Response],
    *,
    max_retries: int,
    base_delay: float = 0.5,
) -> httpx.Response:
    """Retry HTTP requests on 429 and 5xx with exponential backoff."""
    attempt = 0
    while True:
        response = request_fn()
        if response.status_code not in (429, 500, 502, 503, 504):
            return response
        if attempt >= max_retries:
            return response
        delay = base_delay * (2**attempt)
        time.sleep(delay)
        attempt += 1


async def async_request_with_retry(
    request_fn: Callable[[], Awaitable[httpx.Response]],
    *,
    max_retries: int,
    base_delay: float = 0.5,
) -> httpx.Response:
    """Async retry HTTP requests on 429 and 5xx with exponential backoff."""
    attempt = 0
    while True:
        response = await request_fn()
        if response.status_code not in (429, 500, 502, 503, 504):
            return response
        if attempt >= max_retries:
            return response
        delay = base_delay * (2**attempt)
        await asyncio.sleep(delay)
        attempt += 1
