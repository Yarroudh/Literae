from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.api.schemas import ResearchFilters


class SearchPlan(BaseModel):
    query: str = Field(default="", max_length=1_000)
    from_year: int | None = Field(default=None, ge=1000, le=2100)
    to_year: int | None = Field(default=None, ge=1000, le=2100)
    work_type: str | None = Field(default=None, max_length=50)
    open_access: Literal["open", "closed"] | None = None
    language: str | None = Field(default=None, min_length=2, max_length=3)
    author: str | None = Field(default=None, max_length=200)
    authors: list[str] = Field(default_factory=list, max_length=10)
    institution: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=200)
    sort: Literal["relevance", "newest", "oldest", "cited"] | None = None
    intent: Literal[
        "topic_search",
        "author_publications",
        "bibliography",
        "result_analysis",
        "author_overview",
        "more_results",
    ] = "topic_search"


class QueryInterpreter(Protocol):
    async def interpret_search(self, message: str) -> SearchPlan: ...


def merge_search_plan(
    message: str,
    explicit_filters: ResearchFilters,
    extracted: SearchPlan,
) -> tuple[str, ResearchFilters]:
    values: dict[str, object] = {}
    for field_name in ResearchFilters.model_fields:
        explicit_value = getattr(explicit_filters, field_name)
        extracted_value = getattr(extracted, field_name)
        values[field_name] = explicit_value if explicit_value is not None else extracted_value

    query = extracted.query.strip()
    if extracted.intent == "author_publications" and extracted.author:
        query = ""
    fallback_query = (
        "" if values.get("author") and extracted.intent == "author_publications" else message
    )
    return query or fallback_query, ResearchFilters(**values)
