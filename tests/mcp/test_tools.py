from collections.abc import Sequence

import pytest
from mcp import Client

from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult
from app.mcp.client import MCPResearchTools
from app.mcp.server import create_server_from_tools
from app.mcp.tools import (
    FIND_RELATED_WORKS,
    GET_AUTHOR_WORKS,
    GET_CITING_WORKS,
    GET_REFERENCED_WORKS,
    GET_WORK_DETAILS,
    SEARCH_AUTHORS,
    SEARCH_PUBLICATIONS,
)


def publication(identifier: str = "W1") -> ResearchResult:
    return ResearchResult(
        id=identifier,
        title="A research publication",
        authors=["Ada Researcher"],
        year=2025,
        source="Research Journal",
        type="article",
        openAccess=True,
        citedByCount=12,
        topics=["Research"],
        summary="An abstract.",
    )


class FakeResearchTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def search_publications(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        self.calls.append((SEARCH_PUBLICATIONS, (query, filters, page)))
        return [publication()]

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]:
        self.calls.append((SEARCH_AUTHORS, list(names)))
        return [
            AuthorResult(
                id="A1",
                name="Ada Researcher",
                worksCount=10,
                citedByCount=50,
                hIndex=4,
                i10Index=2,
                affiliations=["Example University"],
                topics=["Research"],
                openAlexUrl="https://openalex.org/A1",
            )
        ]

    async def get_author_works(
        self, author: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        self.calls.append((GET_AUTHOR_WORKS, (author, filters, page)))
        return [publication("W2")]

    async def get_work_details(self, work_id: str) -> ResearchResult | None:
        self.calls.append((GET_WORK_DETAILS, work_id))
        return publication(work_id)

    async def find_related_works(self, work_id: str) -> list[ResearchResult]:
        self.calls.append((FIND_RELATED_WORKS, work_id))
        return [publication("W3")]

    async def get_citing_works(self, work_id: str) -> list[ResearchResult]:
        self.calls.append((GET_CITING_WORKS, work_id))
        return [publication("W4")]

    async def get_referenced_works(self, work_id: str) -> list[ResearchResult]:
        self.calls.append((GET_REFERENCED_WORKS, work_id))
        return [publication("W5")]


@pytest.mark.asyncio
async def test_server_exposes_the_academic_research_tool_catalogue() -> None:
    server = create_server_from_tools(FakeResearchTools())
    async with Client(server) as client:
        result = await client.list_tools()

    assert {tool.name for tool in result.tools} == {
        SEARCH_PUBLICATIONS,
        SEARCH_AUTHORS,
        GET_AUTHOR_WORKS,
        GET_WORK_DETAILS,
        FIND_RELATED_WORKS,
        GET_CITING_WORKS,
        GET_REFERENCED_WORKS,
    }


@pytest.mark.asyncio
async def test_typed_client_round_trips_structured_mcp_results() -> None:
    provider = FakeResearchTools()
    client = MCPResearchTools(create_server_from_tools(provider))

    works = await client.search_publications(
        "urban greenery", ResearchFilters(fromYear=2020), page=2
    )
    authors = await client.search_authors(["Ada Researcher"])
    author_works = await client.get_author_works("Ada Researcher", ResearchFilters(sort="cited"))
    details = await client.get_work_details("W9")
    related = await client.find_related_works("W9")
    citing = await client.get_citing_works("W9")
    referenced = await client.get_referenced_works("W9")

    assert works[0].id == "W1"
    assert authors[0].h_index == 4
    assert author_works[0].id == "W2"
    assert details is not None and details.id == "W9"
    assert [item.id for item in related + citing + referenced] == ["W3", "W4", "W5"]
    assert [name for name, _ in provider.calls] == [
        SEARCH_PUBLICATIONS,
        SEARCH_AUTHORS,
        GET_AUTHOR_WORKS,
        GET_WORK_DETAILS,
        FIND_RELATED_WORKS,
        GET_CITING_WORKS,
        GET_REFERENCED_WORKS,
    ]
