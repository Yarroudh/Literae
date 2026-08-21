from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ResearchFilters(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_year: int | None = Field(default=None, alias="fromYear", ge=1000, le=2100)
    to_year: int | None = Field(default=None, alias="toYear", ge=1000, le=2100)
    work_type: str | None = Field(default=None, alias="workType", max_length=50)
    open_access: Literal["open", "closed"] | None = Field(default=None, alias="openAccess")
    language: str | None = Field(default=None, min_length=2, max_length=3)
    author: str | None = Field(default=None, max_length=200)
    institution: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=200)
    sort: Literal["relevance", "newest", "oldest", "cited"] = "relevance"


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(min_length=1, max_length=4_000)
    filters: ResearchFilters = Field(default_factory=ResearchFilters)
    conversation_id: str | None = Field(default=None, alias="conversationId", max_length=100)


class ResearchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: str
    title: str
    authors: list[str]
    year: int
    source: str
    type: str
    open_access: bool = Field(alias="openAccess")
    cited_by_count: int = Field(alias="citedByCount", ge=0)
    topics: list[str]
    summary: str
    doi: HttpUrl | None = None


class AuthorResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    id: str
    name: str
    orcid: HttpUrl | None = None
    works_count: int = Field(alias="worksCount", ge=0)
    cited_by_count: int = Field(alias="citedByCount", ge=0)
    h_index: int = Field(alias="hIndex", ge=0)
    i10_index: int = Field(alias="i10Index", ge=0)
    affiliations: list[str]
    topics: list[str]
    openalex_url: HttpUrl = Field(alias="openAlexUrl")


class ChatResponse(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)

    conversation_id: str = Field(alias="conversationId")
    answer: str
    results: list[ResearchResult]
    show_results: bool = Field(default=True, alias="showResults")
    authors: list[AuthorResult] = Field(default_factory=list)
    show_authors: bool = Field(default=False, alias="showAuthors")
    context_type: Literal["papers", "authors"] | None = Field(
        default=None, alias="contextType"
    )
    suggestions: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    name: str
    version: str
