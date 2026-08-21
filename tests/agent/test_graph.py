from collections.abc import Sequence

import pytest

from app.agent.graph import LangGraphResearchWorkflow
from app.agent.query_understanding import SearchPlan
from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult


class FakeInterpreter:
    async def interpret_search(self, message: str) -> SearchPlan:
        if "Compare these researcher" in message:
            return SearchPlan(intent="author_overview")
        if "h-index" in message:
            return SearchPlan(
                author="Anass Yarroudh",
                authors=["Anass Yarroudh"],
                intent="author_overview",
            )
        return SearchPlan(query=message, intent="topic_search")


class FakeSearcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search(
        self, query: str, filters: ResearchFilters, *, page: int = 1
    ) -> list[ResearchResult]:
        self.calls.append((query, page))
        return [
            ResearchResult(
                id=f"W{page}",
                title=f"Paper page {page}",
                authors=["Ada Researcher"],
                year=2024,
                source="Example Journal",
                type="article",
                openAccess=True,
                citedByCount=1,
                topics=["Research"],
                summary="A research paper.",
            )
        ]

    async def search_authors(self, names: Sequence[str]) -> list[AuthorResult]:
        return [
            AuthorResult(
                id="A5093964800",
                name="Anass Yarroudh",
                orcid="https://orcid.org/0000-0003-1387-8288",
                worksCount=9,
                citedByCount=37,
                hIndex=4,
                i10Index=1,
                affiliations=["University of Liège"],
                topics=["Remote Sensing and LiDAR Applications"],
                openAlexUrl="https://openalex.org/A5093964800",
            )
        ]


class FakeAnswerGenerator:
    def __init__(self) -> None:
        self.paper_calls = 0
        self.questions: list[str] = []

    async def generate_answer(
        self, question: str, evidence: Sequence[dict[str, object]]
    ) -> str:
        self.paper_calls += 1
        self.questions.append(question)
        return f"Answered {question} with {len(evidence)} paper."

    async def generate_author_answer(
        self, question: str, authors: Sequence[dict[str, object]]
    ) -> str:
        return f"Found {len(authors)} author profile."


def make_workflow(searcher: FakeSearcher) -> LangGraphResearchWorkflow:
    return LangGraphResearchWorkflow(
        query_interpreter=FakeInterpreter(),
        research_searcher=searcher,
        answer_generator=FakeAnswerGenerator(),
    )


@pytest.mark.asyncio
async def test_bibtex_is_generated_deterministically_from_current_papers() -> None:
    searcher = FakeSearcher()
    generator = FakeAnswerGenerator()
    workflow = LangGraphResearchWorkflow(
        query_interpreter=FakeInterpreter(),
        research_searcher=searcher,
        answer_generator=generator,
    )
    await workflow.run(
        conversation_id="conversation-bibtex",
        message="Find papers about urban digital twins",
        filters=ResearchFilters(),
    )
    answer, _, show_results, _, _, _, suggestions = await workflow.run(
        conversation_id="conversation-bibtex",
        message="Give me BibTeX code for these papers",
        filters=ResearchFilters(),
    )

    assert answer.startswith("```bibtex\n@article{researcher2024")
    assert "title = {Paper page 1}" in answer
    assert show_results is False
    assert generator.paper_calls == 1
    assert "Give me an overview of the authors represented here" in suggestions


@pytest.mark.asyncio
async def test_ris_is_generated_deterministically_from_current_papers() -> None:
    searcher = FakeSearcher()
    workflow = make_workflow(searcher)
    await workflow.run(
        conversation_id="conversation-ris",
        message="Find papers about urban digital twins",
        filters=ResearchFilters(),
    )
    answer, _, show_results, _, _, _, _ = await workflow.run(
        conversation_id="conversation-ris",
        message="Give me RIS code for these papers",
        filters=ResearchFilters(),
    )

    assert answer.startswith("```ris\nTY  - JOUR")
    assert "TI  - Paper page 1" in answer
    assert "ER  -" in answer
    assert show_results is False


@pytest.mark.asyncio
async def test_revision_follow_up_reuses_papers_and_previous_answer() -> None:
    searcher = FakeSearcher()
    generator = FakeAnswerGenerator()
    workflow = LangGraphResearchWorkflow(
        query_interpreter=FakeInterpreter(),
        research_searcher=searcher,
        answer_generator=generator,
    )
    await workflow.run(
        conversation_id="conversation-revision",
        message='Draft a "Related work" section from these papers',
        filters=ResearchFilters(),
    )
    _, _, show_results, _, _, context_type, _ = await workflow.run(
        conversation_id="conversation-revision",
        message="make it longer",
        filters=ResearchFilters(),
    )

    assert searcher.calls == [('Draft a "Related work" section from these papers', 1)]
    assert show_results is False
    assert context_type == "papers"
    assert "Previous response:" in generator.questions[-1]
    assert "Follow-up instruction:\nmake it longer" in generator.questions[-1]


@pytest.mark.asyncio
async def test_reference_follow_up_reuses_papers_and_hides_cards() -> None:
    searcher = FakeSearcher()
    workflow = make_workflow(searcher)

    _, initial_results, initial_show_results, _, _, _, _ = await workflow.run(
        conversation_id="conversation-1",
        message="Find papers about urban digital twins",
        filters=ResearchFilters(),
    )
    answer, follow_up_results, follow_up_show_results, _, _, context_type, suggestions = await workflow.run(
        conversation_id="conversation-1",
        message="Format these references in APA 7",
        filters=ResearchFilters(),
    )

    assert searcher.calls == [("Find papers about urban digital twins", 1)]
    assert initial_show_results is True
    assert initial_results[0].id == "W1"
    assert follow_up_show_results is False
    assert follow_up_results[0].id == "W1"
    assert "APA 7" in answer
    assert context_type == "papers"
    assert "Give me BibTeX code for these papers" in suggestions
    assert "Give me RIS code for these papers" in suggestions


@pytest.mark.asyncio
async def test_more_papers_continues_the_previous_search_on_the_next_page() -> None:
    searcher = FakeSearcher()
    workflow = make_workflow(searcher)

    await workflow.run(
        conversation_id="conversation-1",
        message="Find papers about urban digital twins",
        filters=ResearchFilters(),
    )
    _, results, show_results, _, _, _, _ = await workflow.run(
        conversation_id="conversation-1",
        message="Find more papers",
        filters=ResearchFilters(),
    )

    assert searcher.calls == [
        ("Find papers about urban digital twins", 1),
        ("Find papers about urban digital twins", 2),
    ]
    assert results[0].id == "W2"
    assert show_results is True


@pytest.mark.asyncio
async def test_author_metrics_request_uses_author_profiles_not_publications() -> None:
    searcher = FakeSearcher()
    workflow = make_workflow(searcher)

    answer, results, show_results, authors, show_authors, context_type, suggestions = await workflow.run(
        conversation_id="conversation-author",
        message="What is the h-index and ORCID of Anass Yarroudh?",
        filters=ResearchFilters(),
    )

    assert searcher.calls == []
    assert results == []
    assert show_results is False
    assert show_authors is True
    assert authors[0].h_index == 4
    assert authors[0].orcid is not None
    assert answer == "Found 1 author profile."
    assert context_type == "authors"
    assert suggestions[0] == "Show the most cited papers by Anass Yarroudh"

    _, _, _, retained_authors, repeated_cards, retained_context, _ = await workflow.run(
        conversation_id="conversation-author",
        message="Compare these researcher profiles",
        filters=ResearchFilters(),
    )

    assert retained_authors[0].id == "A5093964800"
    assert repeated_cards is False
    assert retained_context == "authors"
