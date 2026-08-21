from collections.abc import Mapping, Sequence
from typing import Any

from mcp import Client
from mcp.server import MCPServer

from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult
from app.mcp.tools import (
    FIND_RELATED_WORKS,
    GET_AUTHOR_WORKS,
    GET_CITING_WORKS,
    GET_REFERENCED_WORKS,
    GET_WORK_DETAILS,
    SEARCH_AUTHORS,
    SEARCH_PUBLICATIONS,
    AuthorToolResult,
    PublicationToolResult,
    ResearchTools,
    WorkToolResult,
)


class MCPResearchTools(ResearchTools):
    """Typed client for Literae's MCP research server."""

    def __init__(self, server: MCPServer) -> None:
        self._server = server

    async def _call(self, name: str, arguments: dict[str, Any]) -> Mapping[str, Any]:
        async with Client(self._server, raise_exceptions=True) as client:
            result = await client.call_tool(name, arguments)
        if result.is_error or not isinstance(result.structured_content, Mapping):
            raise RuntimeError(f"MCP tool {name} returned an invalid result")
        return result.structured_content

    async def search_publications(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        payload = await self._call(
            SEARCH_PUBLICATIONS,
            {
                "query": query,
                "filters": filters.model_dump(mode="json", by_alias=True),
                "page": page,
            },
        )
        return PublicationToolResult.model_validate(payload).publications

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]:
        payload = await self._call(SEARCH_AUTHORS, {"names": list(names)})
        return AuthorToolResult.model_validate(payload).authors

    async def get_author_works(
        self, author: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        payload = await self._call(
            GET_AUTHOR_WORKS,
            {
                "author": author,
                "filters": filters.model_dump(mode="json", by_alias=True),
                "page": page,
            },
        )
        return PublicationToolResult.model_validate(payload).publications

    async def get_work_details(self, work_id: str) -> ResearchResult | None:
        payload = await self._call(GET_WORK_DETAILS, {"work_id": work_id})
        return WorkToolResult.model_validate(payload).publication

    async def find_related_works(self, work_id: str) -> list[ResearchResult]:
        payload = await self._call(FIND_RELATED_WORKS, {"work_id": work_id})
        return PublicationToolResult.model_validate(payload).publications

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]:
        payload = await self._call(GET_CITING_WORKS, {"work_id": work_id})
        return PublicationToolResult.model_validate(payload).publications

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]:
        payload = await self._call(GET_REFERENCED_WORKS, {"work_id": work_id})
        return PublicationToolResult.model_validate(payload).publications
