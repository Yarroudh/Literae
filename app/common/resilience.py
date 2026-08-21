import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import cast

from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult
from app.retrieval.openalex import OpenAlexTransientError, ResearchSearcher


class AsyncTTLCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 256) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._values: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()

    async def get_or_create[T](self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        if self._ttl_seconds == 0:
            return await factory()
        now = time.monotonic()
        async with self._lock:
            cached = self._values.get(key)
            if cached is not None and cached[0] > now:
                return cast(T, cached[1])
        value = await factory()
        async with self._lock:
            if len(self._values) >= self._max_entries:
                oldest = min(self._values, key=lambda item: self._values[item][0])
                self._values.pop(oldest, None)
            self._values[key] = (time.monotonic() + self._ttl_seconds, value)
        return value


async def retry_transient[T](
    operation: Callable[[], Awaitable[T]], *, attempts: int = 3, base_delay: float = 0.2
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except OpenAlexTransientError:
            if attempt == attempts:
                raise
            await asyncio.sleep(base_delay * 2 ** (attempt - 1))
    raise RuntimeError("Retry loop ended unexpectedly")


class ResilientResearchSearcher:
    def __init__(
        self, searcher: ResearchSearcher, *, cache_ttl_seconds: int = 300, retry_attempts: int = 3
    ) -> None:
        self._searcher = searcher
        self._cache = AsyncTTLCache(cache_ttl_seconds)
        self._retry_attempts = retry_attempts

    async def search(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        key = _cache_key("search", query, filters.model_dump(mode="json"), page)
        return await self._cached(key, lambda: self._searcher.search(query, filters, page=page))

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]:
        normalized = [name.strip() for name in names]
        return await self._cached(
            _cache_key("authors", normalized), lambda: self._searcher.search_authors(normalized)
        )

    async def get_work(self, work_id: str) -> ResearchResult | None:
        return await self._cached(
            _cache_key("work", work_id), lambda: self._searcher.get_work(work_id)
        )

    async def get_related_works(self, work_id: str) -> list[ResearchResult]:
        return await self._cached(
            _cache_key("related", work_id), lambda: self._searcher.get_related_works(work_id)
        )

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]:
        return await self._cached(
            _cache_key("citing", work_id), lambda: self._searcher.get_citing_works(work_id)
        )

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]:
        return await self._cached(
            _cache_key("referenced", work_id),
            lambda: self._searcher.get_referenced_works(work_id),
        )

    async def _cached[T](self, key: str, operation: Callable[[], Awaitable[T]]) -> T:
        return await self._cache.get_or_create(
            key, lambda: retry_transient(operation, attempts=self._retry_attempts)
        )


def _cache_key(*parts: object) -> str:
    return json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
