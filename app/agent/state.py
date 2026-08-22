from typing import NotRequired, TypedDict

from app.agent.query_understanding import SearchPlan
from app.api.schemas import ResearchFilters


class ResearchState(TypedDict):
    message: str
    explicit_filters: ResearchFilters
    search_plan: NotRequired[SearchPlan]
    search_query: NotRequired[str]
    search_filters: NotRequired[ResearchFilters]
    results: NotRequired[list[dict[str, object]]]
    answer: NotRequired[str]
    page: NotRequired[int]
    route: NotRequired[str]
    show_results: NotRequired[bool]
    authors: NotRequired[list[dict[str, object]]]
    show_authors: NotRequired[bool]
    context_type: NotRequired[str]
    resolved_context: NotRequired[str]
    validation_issue: NotRequired[str]
    selected_results: NotRequired[list[dict[str, object]]]
    action: NotRequired[str]
    suggestions: NotRequired[list[str]]
    previous_answer: NotRequired[str]
    included_result_ids: NotRequired[list[str]]
