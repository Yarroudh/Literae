from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult
from app.retrieval.openalex import ResearchSearcher

SEARCH_PUBLICATIONS = "search_publications"
SEARCH_AUTHORS = "search_authors"
GET_AUTHOR_WORKS = "get_author_works"
GET_WORK_DETAILS = "get_work_details"
FIND_RELATED_WORKS = "find_related_works"
GET_CITING_WORKS = "get_citing_works"
GET_REFERENCED_WORKS = "get_referenced_works"


class PublicationToolResult(BaseModel):
    publications: list[ResearchResult] = Field(default_factory=list)


class AuthorToolResult(BaseModel):
    authors: list[AuthorResult] = Field(default_factory=list)


class WorkToolResult(BaseModel):
    publication: ResearchResult | None = None


class ResearchTools(Protocol):
    async def search_publications(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]: ...

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]: ...

    async def get_author_works(
        self, author: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]: ...

    async def get_work_details(self, work_id: str) -> ResearchResult | None: ...

    async def find_related_works(self, work_id: str) -> list[ResearchResult]: ...

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]: ...

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]: ...


class OpenAlexResearchTools:
    """Typed tool implementation exposed by the Literae MCP server."""

    def __init__(self, searcher: ResearchSearcher) -> None:
        self._searcher = searcher

    async def search_publications(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        return await self._searcher.search(query, filters, page=page)

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]:
        return await self._searcher.search_authors(names)

    async def get_author_works(
        self, author: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        author_filters = filters.model_copy(update={"author": author})
        return await self._searcher.search("", author_filters, page=page)

    async def get_work_details(self, work_id: str) -> ResearchResult | None:
        return await self._searcher.get_work(work_id)

    async def find_related_works(self, work_id: str) -> list[ResearchResult]:
        return await self._searcher.get_related_works(work_id)

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]:
        return await self._searcher.get_citing_works(work_id)

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]:
        return await self._searcher.get_referenced_works(work_id)
