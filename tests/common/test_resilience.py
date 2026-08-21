import pytest

from app.api.schemas import ResearchFilters, ResearchResult
from app.common.resilience import ResilientResearchSearcher
from app.retrieval.openalex import OpenAlexTransientError


class FlakySearcher:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, filters: ResearchFilters, *, page: int = 1):
        self.calls += 1
        if self.calls == 1:
            raise OpenAlexTransientError("temporary")
        return [
            ResearchResult(
                id="W1",
                title="Cached work",
                authors=[],
                year=2025,
                source="Journal",
                type="article",
                openAccess=True,
                citedByCount=0,
                topics=[],
                summary="Summary",
            )
        ]


@pytest.mark.asyncio
async def test_research_search_retries_transient_failures_and_caches_success() -> None:
    source = FlakySearcher()
    searcher = ResilientResearchSearcher(source, cache_ttl_seconds=60, retry_attempts=2)

    first = await searcher.search("sleep", ResearchFilters())
    second = await searcher.search("sleep", ResearchFilters())

    assert first[0].id == "W1"
    assert second[0].id == "W1"
    assert source.calls == 2
