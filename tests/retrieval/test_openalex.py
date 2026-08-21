from typing import Any

import httpx
import pytest

from app.api.schemas import ResearchFilters
from app.retrieval.openalex import OpenAlexClient, OpenAlexError


def openalex_work(**overrides: Any) -> dict[str, Any]:
    work = {
        "id": "https://openalex.org/W123",
        "display_name": "Green spaces and wellbeing",
        "publication_year": 2024,
        "type": "article",
        "authorships": [
            {"author": {"display_name": "Ada Researcher"}},
            {"author": {"display_name": "Sam Scholar"}},
        ],
        "primary_location": {"source": {"display_name": "Nature Cities"}},
        "open_access": {"is_oa": True},
        "cited_by_count": 18,
        "topics": [
            {"display_name": "Urban Health"},
            {"display_name": "Environmental Psychology"},
        ],
        "abstract_inverted_index": {
            "Green": [0],
            "spaces": [1],
            "support": [2],
            "wellbeing.": [3],
        },
        "doi": "https://doi.org/10.1000/green",
    }
    work.update(overrides)
    return work


@pytest.mark.asyncio
async def test_search_translates_filters_and_normalizes_works() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        entity_ids = {
            "/authors": "https://openalex.org/A123",
            "/institutions": "https://openalex.org/I456",
            "/sources": "https://openalex.org/S789",
        }
        if request.url.path in entity_ids:
            return httpx.Response(200, json={"results": [{"id": entity_ids[request.url.path]}]})
        captured_request = request
        return httpx.Response(200, json={"results": [openalex_work()]})

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = OpenAlexClient(
            client=http_client,
            api_key="test-key",
            email="researcher@example.com",
            results_limit=6,
        )
        results = await client.search(
            "urban green spaces",
            ResearchFilters(
                fromYear=2020,
                toYear=2025,
                workType="article",
                openAccess="open",
                language="en",
                author="Ada Researcher",
                institution="Example University",
                source="Nature Cities",
                sort="cited",
            ),
        )

    assert captured_request is not None
    params = captured_request.url.params
    assert params["search"] == "urban green spaces"
    assert params["per-page"] == "6"
    assert params["sort"] == "cited_by_count:desc"
    assert "from_publication_date:2020-01-01" in params["filter"]
    assert "to_publication_date:2025-12-31" in params["filter"]
    assert "type:article" in params["filter"]
    assert "is_oa:true" in params["filter"]
    assert "language:en" in params["filter"]
    assert "author.id:A123" in params["filter"]
    assert "institution.id:I456" in params["filter"]
    assert "primary_location.source.id:S789" in params["filter"]
    assert params["api_key"] == "test-key"
    assert params["mailto"] == "researcher@example.com"

    assert len(results) == 1
    result = results[0]
    assert result.id == "W123"
    assert result.authors == ["Ada Researcher", "Sam Scholar"]
    assert result.source == "Nature Cities"
    assert result.open_access is True
    assert result.summary == "Green spaces support wellbeing."
    assert str(result.doi) == "https://doi.org/10.1000/green"


@pytest.mark.asyncio
async def test_search_skips_incomplete_works_and_handles_missing_optional_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    openalex_work(id=None),
                    openalex_work(
                        id="https://openalex.org/W456",
                        authorships=None,
                        primary_location=None,
                        open_access=None,
                        topics=None,
                        abstract_inverted_index=None,
                        doi=None,
                    ),
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        results = await OpenAlexClient(client=http_client).search(
            "wellbeing", ResearchFilters()
        )

    assert len(results) == 1
    assert results[0].id == "W456"
    assert results[0].authors == []
    assert results[0].source == "Unknown source"
    assert results[0].summary == "No abstract is available for this publication."
    assert results[0].doi is None


@pytest.mark.asyncio
async def test_search_maps_invalid_responses_to_a_domain_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = OpenAlexClient(client=http_client)
        with pytest.raises(OpenAlexError, match="invalid response"):
            await client.search("a topic", ResearchFilters())


@pytest.mark.asyncio
async def test_search_returns_no_works_when_a_named_filter_cannot_be_resolved() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        results = await OpenAlexClient(client=http_client).search(
            "a topic", ResearchFilters(author="No Matching Author")
        )

    assert results == []
    assert requested_paths == ["/authors"]


@pytest.mark.asyncio
async def test_author_catalog_request_does_not_search_for_the_instruction_text() -> None:
    works_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal works_request
        if request.url.path == "/authors":
            assert request.url.params["search"] == "Anass Yarroudh"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "https://openalex.org/A5093964800",
                            "display_name": "Anass Yarroudh",
                        }
                    ]
                },
            )
        works_request = request
        return httpx.Response(200, json={"results": [openalex_work()]})

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        results = await OpenAlexClient(client=http_client).search(
            "Can you find all papers of this author",
            ResearchFilters(author="Anass Yarroudh"),
        )

    assert works_request is not None
    assert "search" not in works_request.url.params
    assert works_request.url.params["filter"] == "author.id:A5093964800"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_topic_search_is_preserved_when_an_author_filter_is_active() -> None:
    works_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal works_request
        if request.url.path == "/authors":
            return httpx.Response(
                200, json={"results": [{"id": "https://openalex.org/A5093964800"}]}
            )
        works_request = request
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        await OpenAlexClient(client=http_client).search(
            "digital twins for railway infrastructure",
            ResearchFilters(author="Anass Yarroudh"),
        )

    assert works_request is not None
    assert works_request.url.params["search"] == "digital twins for railway infrastructure"


@pytest.mark.asyncio
async def test_search_authors_normalizes_openalex_metrics_and_identifiers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/authors"
        assert request.url.params["search"] == "Anass Yarroudh"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/A5093964800",
                        "display_name": "Anass Yarroudh",
                        "orcid": "https://orcid.org/0000-0003-1387-8288",
                        "works_count": 9,
                        "cited_by_count": 37,
                        "summary_stats": {"h_index": 4, "i10_index": 1},
                        "affiliations": [
                            {"institution": {"display_name": "University of Liège"}}
                        ],
                        "topics": [
                            {"display_name": "Remote Sensing and LiDAR Applications"},
                            {"display_name": "3D Modeling in Geospatial Applications"},
                        ],
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="https://api.openalex.org",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        authors = await OpenAlexClient(client=http_client).search_authors(["Anass Yarroudh"])

    assert len(authors) == 1
    author = authors[0]
    assert author.id == "A5093964800"
    assert author.works_count == 9
    assert author.cited_by_count == 37
    assert author.h_index == 4
    assert author.i10_index == 1
    assert author.affiliations == ["University of Liège"]
    assert author.topics == [
        "Remote Sensing and LiDAR Applications",
        "3D Modeling in Geospatial Applications",
    ]
    assert str(author.orcid) == "https://orcid.org/0000-0003-1387-8288"
