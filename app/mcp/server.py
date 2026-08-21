from typing import Any

from mcp.server import MCPServer

from app.api.schemas import ResearchFilters
from app.config.settings import get_settings
from app.mcp.tools import (
    FIND_RELATED_WORKS,
    GET_AUTHOR_WORKS,
    GET_CITING_WORKS,
    GET_REFERENCED_WORKS,
    GET_WORK_DETAILS,
    SEARCH_AUTHORS,
    SEARCH_PUBLICATIONS,
    AuthorToolResult,
    OpenAlexResearchTools,
    PublicationToolResult,
    ResearchTools,
    WorkToolResult,
)
from app.retrieval.openalex import OpenAlexClient, ResearchSearcher


def create_research_server(searcher: ResearchSearcher) -> MCPServer:
    return create_server_from_tools(OpenAlexResearchTools(searcher))


def create_server_from_tools(tools: ResearchTools) -> MCPServer:
    server = MCPServer(
        "literae-research",
        title="Literae Academic Research Tools",
        instructions="Use these tools only for scholarly publication and researcher discovery.",
    )

    @server.tool(name=SEARCH_PUBLICATIONS, structured_output=True)
    async def search_publications(
        query: str, filters: dict[str, Any] | None = None, page: int = 1
    ) -> PublicationToolResult:
        """Search scholarly publications using an academic query and optional filters."""
        validated = ResearchFilters.model_validate(filters or {})
        publications = await tools.search_publications(query, validated, page=max(page, 1))
        return PublicationToolResult(publications=publications)

    @server.tool(name=SEARCH_AUTHORS, structured_output=True)
    async def search_authors(names: list[str]) -> AuthorToolResult:
        """Find researcher profiles and bibliometric information by name."""
        return AuthorToolResult(authors=await tools.search_authors(names))

    @server.tool(name=GET_AUTHOR_WORKS, structured_output=True)
    async def get_author_works(
        author: str, filters: dict[str, Any] | None = None, page: int = 1
    ) -> PublicationToolResult:
        """List publications belonging to a named researcher."""
        validated = ResearchFilters.model_validate(filters or {})
        publications = await tools.get_author_works(author, validated, page=max(page, 1))
        return PublicationToolResult(publications=publications)

    @server.tool(name=GET_WORK_DETAILS, structured_output=True)
    async def get_work_details(work_id: str) -> WorkToolResult:
        """Get one publication by its OpenAlex work identifier."""
        return WorkToolResult(publication=await tools.get_work_details(work_id))

    @server.tool(name=FIND_RELATED_WORKS, structured_output=True)
    async def find_related_works(work_id: str) -> PublicationToolResult:
        """Find publications related to an OpenAlex work."""
        return PublicationToolResult(publications=await tools.find_related_works(work_id))

    @server.tool(name=GET_CITING_WORKS, structured_output=True)
    async def get_citing_works(work_id: str) -> PublicationToolResult:
        """Find publications that cite an OpenAlex work."""
        return PublicationToolResult(publications=await tools.get_citing_works(work_id))

    @server.tool(name=GET_REFERENCED_WORKS, structured_output=True)
    async def get_referenced_works(work_id: str) -> PublicationToolResult:
        """Get publications referenced by an OpenAlex work."""
        return PublicationToolResult(publications=await tools.get_referenced_works(work_id))

    return server


def create_configured_research_server() -> MCPServer:
    settings = get_settings()
    api_key = (
        settings.openalex_api_key.get_secret_value()
        if settings.openalex_api_key is not None
        else None
    )
    searcher = OpenAlexClient(
        base_url=settings.openalex_base_url,
        api_key=api_key,
        email=settings.openalex_email,
        results_limit=settings.openalex_results_limit,
        timeout_seconds=settings.openalex_timeout_seconds,
    )
    return create_research_server(searcher)


def main() -> None:
    create_configured_research_server().run()


if __name__ == "__main__":
    main()
