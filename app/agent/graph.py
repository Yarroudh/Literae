import re
from collections.abc import Mapping
from typing import Literal, Protocol

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.query_understanding import QueryInterpreter, SearchPlan, merge_search_plan
from app.agent.state import ResearchState
from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult
from app.debugging.laminar import trace_span, traced_node
from app.llm.deepseek import AnswerGenerator
from app.mcp.client import MCPResearchTools
from app.mcp.server import create_research_server
from app.mcp.tools import ResearchTools
from app.retrieval.openalex import ResearchSearcher


class ResearchWorkflow(Protocol):
    async def run(
        self,
        *,
        conversation_id: str,
        message: str,
        filters: ResearchFilters,
        context: Mapping[str, object] | None = None,
        included_result_ids: list[str] | None = None,
    ) -> tuple[
        str, list[ResearchResult], bool, list[AuthorResult], bool, str | None, list[str]
    ]: ...


class LangGraphResearchWorkflow:
    def __init__(
        self,
        *,
        query_interpreter: QueryInterpreter,
        research_searcher: ResearchSearcher,
        answer_generator: AnswerGenerator,
        research_tools: ResearchTools | None = None,
    ) -> None:
        self._query_interpreter = query_interpreter
        self._research_tools = research_tools or MCPResearchTools(
            create_research_server(research_searcher)
        )
        self._answer_generator = answer_generator
        builder = StateGraph(ResearchState)
        builder.add_node(
            "interpret_request", traced_node("interpret_request", self._interpret_request)
        )
        builder.add_node("resolve_context", traced_node("resolve_context", self._resolve_context))
        builder.add_node(
            "validate_search_plan", traced_node("validate_search_plan", self._validate_search_plan)
        )
        builder.add_node("route_request", traced_node("route_request", self._route_request))
        builder.add_node(
            "search_publications", traced_node("search_publications", self._search_publications)
        )
        builder.add_node("search_authors", traced_node("search_authors", self._search_authors))
        builder.add_node(
            "get_work_details", traced_node("get_work_details", self._get_work_details)
        )
        builder.add_node(
            "find_related_works", traced_node("find_related_works", self._find_related_works)
        )
        builder.add_node(
            "get_citing_works", traced_node("get_citing_works", self._get_citing_works)
        )
        builder.add_node(
            "get_referenced_works",
            traced_node("get_referenced_works", self._get_referenced_works),
        )
        builder.add_node("select_evidence", traced_node("select_evidence", self._select_evidence))
        builder.add_node(
            "execute_research_action",
            traced_node("execute_research_action", self._execute_research_action),
        )
        builder.add_node("verify_answer", traced_node("verify_answer", self._verify_answer))
        builder.add_node(
            "recover_or_clarify", traced_node("recover_or_clarify", self._recover_or_clarify)
        )
        builder.add_node(
            "generate_followups", traced_node("generate_followups", self._generate_followups)
        )
        builder.add_edge(START, "interpret_request")
        builder.add_edge("interpret_request", "resolve_context")
        builder.add_edge("resolve_context", "validate_search_plan")
        builder.add_edge("validate_search_plan", "route_request")
        builder.add_conditional_edges(
            "route_request",
            self._next_step,
            {
                "search": "search_publications",
                "authors": "search_authors",
                "work_details": "get_work_details",
                "related_works": "find_related_works",
                "citing_works": "get_citing_works",
                "referenced_works": "get_referenced_works",
                "reuse": "select_evidence",
                "recover": "recover_or_clarify",
            },
        )
        builder.add_edge("search_publications", "select_evidence")
        builder.add_edge("search_authors", "select_evidence")
        builder.add_edge("get_work_details", "select_evidence")
        builder.add_edge("find_related_works", "select_evidence")
        builder.add_edge("get_citing_works", "select_evidence")
        builder.add_edge("get_referenced_works", "select_evidence")
        builder.add_edge("select_evidence", "execute_research_action")
        builder.add_conditional_edges(
            "execute_research_action",
            self._after_action,
            {"verify": "verify_answer", "recover": "recover_or_clarify"},
        )
        builder.add_edge("verify_answer", "generate_followups")
        builder.add_edge("recover_or_clarify", "generate_followups")
        builder.add_edge("generate_followups", END)
        self._graph = builder.compile(checkpointer=InMemorySaver())

    async def run(
        self,
        *,
        conversation_id: str,
        message: str,
        filters: ResearchFilters,
        context: Mapping[str, object] | None = None,
        included_result_ids: list[str] | None = None,
    ) -> tuple[str, list[ResearchResult], bool, list[AuthorResult], bool, str | None, list[str]]:
        with trace_span(
            "literae_research_request",
            input_data={"conversation_id": conversation_id, "message": message},
            session_id=conversation_id,
        ):
            input_state: dict[str, object] = {
                "message": message,
                "explicit_filters": filters,
                "included_result_ids": included_result_ids or [],
            }
            if context:
                input_state.update(
                    {
                        "results": context.get("results", []),
                        "authors": context.get("authors", []),
                        "answer": context.get("answer", ""),
                        "context_type": context.get("contextType"),
                    }
                )
            state = await self._graph.ainvoke(
                input_state,
                {"configurable": {"thread_id": conversation_id}},
            )
        results = [ResearchResult.model_validate(result) for result in state.get("results", [])]
        authors = [AuthorResult.model_validate(author) for author in state.get("authors", [])]
        return (
            state["answer"],
            results,
            state.get("show_results", True),
            authors,
            state.get("show_authors", False),
            state.get("context_type"),
            state.get("suggestions", []),
        )

    async def _interpret_request(self, state: ResearchState) -> dict[str, object]:
        previous_answer = state.get("answer", "")
        plan = _context_followup_plan(
            state["message"], state
        ) or await self._query_interpreter.interpret_search(state["message"])
        query, filters = merge_search_plan(state["message"], state["explicit_filters"], plan)
        if state.get("results") and _is_more_results_request(state["message"]):
            plan = plan.model_copy(update={"intent": "more_results"})
            query = state.get("search_query", query)
            filters = state.get("search_filters", filters)
            page = state.get("page", 1) + 1
        else:
            page = 1
        return {
            "search_plan": plan,
            "search_query": query,
            "search_filters": filters,
            "page": page,
            "previous_answer": previous_answer,
        }

    def _resolve_context(self, state: ResearchState) -> dict[str, object]:
        message = state["message"]
        has_papers = bool(state.get("results"))
        has_authors = bool(state.get("authors"))
        if has_papers and (
            _is_current_results_request(message)
            or _is_revision_request(message)
            or state["search_plan"].intent in {"bibliography", "result_analysis", "author_overview"}
        ):
            context = "papers"
        elif has_authors and _is_author_profile_request(message):
            context = "authors"
        else:
            context = "new_search"
        return {"resolved_context": context}

    def _validate_search_plan(self, state: ResearchState) -> dict[str, object]:
        filters = state["search_filters"]
        issue = None
        if filters.from_year and filters.to_year and filters.from_year > filters.to_year:
            issue = "The start year must be earlier than the end year."
        return {"validation_issue": issue}

    def _route_request(self, state: ResearchState) -> dict[str, object]:
        reusable_intents = {"bibliography", "result_analysis", "author_overview"}
        message = state["message"]
        plan = state["search_plan"]
        should_reuse = state.get("resolved_context") == "papers" and (
            _is_current_results_request(message)
            or _is_revision_request(message)
            or plan.intent in reusable_intents
        )
        wants_authors = plan.intent == "author_overview" or _is_author_profile_request(message)
        work_routes = {
            "work_details",
            "related_works",
            "citing_works",
            "referenced_works",
        }
        reuses_current_authors = bool(state.get("authors")) and not plan.authors and not plan.author
        if plan.intent == "unsupported":
            route = "recover"
        elif plan.intent in work_routes:
            route = plan.intent
        elif wants_authors:
            route = "authors"
        elif should_reuse and not _is_more_results_request(message):
            route = "reuse"
        else:
            route = "search"
        return {
            "route": route,
            "show_results": route == "search" or route in work_routes,
            "show_authors": route == "authors" and not reuses_current_authors,
        }

    def _next_step(
        self, state: ResearchState
    ) -> Literal[
        "search",
        "authors",
        "work_details",
        "related_works",
        "citing_works",
        "referenced_works",
        "reuse",
        "recover",
    ]:
        if state.get("validation_issue"):
            return "recover"
        if state["route"] == "recover":
            return "recover"
        if state["route"] == "authors":
            return "authors"
        if state["route"] == "work_details":
            return "work_details"
        if state["route"] == "related_works":
            return "related_works"
        if state["route"] == "citing_works":
            return "citing_works"
        if state["route"] == "referenced_works":
            return "referenced_works"
        return "reuse" if state["route"] == "reuse" else "search"

    async def _search_publications(self, state: ResearchState) -> dict[str, object]:
        plan = state["search_plan"]
        if plan.intent == "author_publications" and state["search_filters"].author:
            results = await self._research_tools.get_author_works(
                state["search_filters"].author,
                state["search_filters"],
                page=state.get("page", 1),
            )
        else:
            results = await self._research_tools.search_publications(
                state["search_query"], state["search_filters"], page=state.get("page", 1)
            )
            broader_query = _broader_review_query(state["search_query"])
            if not results and broader_query:
                results = await self._research_tools.search_publications(
                    broader_query,
                    state["search_filters"],
                    page=state.get("page", 1),
                )
        return {
            "results": [result.model_dump(mode="json", by_alias=True) for result in results],
            "context_type": "papers",
        }

    async def _search_authors(self, state: ResearchState) -> dict[str, object]:
        plan = state["search_plan"]
        names = plan.authors or ([plan.author] if plan.author else [])
        if not names:
            names = _author_names_from_results(_considered_results(state))
        if not names and state.get("authors"):
            return {}
        authors = await self._research_tools.search_authors(names)
        return {
            "authors": [author.model_dump(mode="json", by_alias=True) for author in authors],
            "context_type": "authors",
        }

    async def _get_work_details(self, state: ResearchState) -> dict[str, object]:
        work_id = _work_id_for_request(state)
        result = await self._research_tools.get_work_details(work_id) if work_id else None
        return _publication_state([result] if result else [])

    async def _find_related_works(self, state: ResearchState) -> dict[str, object]:
        work_id = _work_id_for_request(state)
        results = await self._research_tools.find_related_works(work_id) if work_id else []
        return _publication_state(results)

    async def _get_citing_works(self, state: ResearchState) -> dict[str, object]:
        work_id = _work_id_for_request(state)
        results = await self._research_tools.get_citing_works(work_id) if work_id else []
        return _publication_state(results)

    async def _get_referenced_works(self, state: ResearchState) -> dict[str, object]:
        work_id = _work_id_for_request(state)
        results = await self._research_tools.get_referenced_works(work_id) if work_id else []
        return _publication_state(results)

    def _select_evidence(self, state: ResearchState) -> dict[str, object]:
        # Every retrieved publication is available by default. Explicit follow-up
        # selections narrow the evidence without applying an arbitrary positional cutoff.
        return {"selected_results": _considered_results(state)}

    async def _execute_research_action(self, state: ResearchState) -> dict[str, object]:
        if state.get("validation_issue"):
            return {"action": "recover"}
        if state.get("route") in {
            "search",
            "work_details",
            "related_works",
            "citing_works",
            "referenced_works",
        } and not state.get("results"):
            return {"action": "recover"}
        if state.get("route") == "authors" and not state.get("authors"):
            return {"action": "recover"}
        message = state["message"]
        if re.search(r"\bbibtex\b", message, re.IGNORECASE):
            return {
                "answer": _format_bibtex(state.get("selected_results", [])),
                "action": "verify",
            }
        if re.search(r"\bris\b", message, re.IGNORECASE):
            return {"answer": _format_ris(state.get("selected_results", [])), "action": "verify"}
        reference_style = _reference_style(message)
        if state["search_plan"].intent == "bibliography" or reference_style:
            return {
                "answer": _format_references(
                    state.get("selected_results", []), reference_style or "APA 7"
                ),
                "action": "verify",
            }
        if state.get("route") == "authors":
            answer = await self._answer_generator.generate_author_answer(
                state["message"], state.get("authors", [])
            )
            return {"answer": answer, "action": "verify"}
        results = state.get("selected_results", [])
        question = state["message"]
        if state["search_plan"].intent == "result_analysis" and not any(
            _has_abstract(result) for result in results
        ):
            return {
                "answer": _format_metadata_only_analysis(results),
                "action": "verify",
            }
        if _is_revision_request(question) and state.get("previous_answer"):
            question = (
                "Revise the previous response according to the follow-up instruction. "
                "Keep it grounded in the same publications.\n\n"
                f"Previous response:\n{state['previous_answer']}\n\n"
                f"Follow-up instruction:\n{question}"
            )
        answer = await self._answer_generator.generate_answer(question, results)
        return {"answer": answer, "action": "verify"}

    def _after_action(self, state: ResearchState) -> Literal["verify", "recover"]:
        return "recover" if state.get("action") == "recover" else "verify"

    def _verify_answer(self, state: ResearchState) -> dict[str, object]:
        answer = state.get("answer", "")
        count = len(state.get("selected_results", []))
        # Remove impossible numeric citations rather than displaying broken references.
        if count:
            answer = re.sub(
                r"\[(\d+)\]",
                lambda match: match.group(0) if int(match.group(1)) <= count else "",
                answer,
            )
        return {"answer": answer.strip()}

    def _recover_or_clarify(self, state: ResearchState) -> dict[str, object]:
        issue = state.get("validation_issue")
        if issue:
            return {"answer": issue, "show_results": False, "show_authors": False}
        if state["search_plan"].intent == "unsupported":
            return {
                "answer": (
                    "Literae is focused on academic research. I can help you find publications, "
                    "explore researchers, compare studies, format references, or work with your "
                    "current sources."
                ),
                "show_results": False,
                "show_authors": False,
            }
        if state.get("route") == "authors":
            answer = (
                "I couldn't identify a matching researcher. Try adding an affiliation or ORCID."
            )
        else:
            answer = "I couldn't find closely related publications. Try broader terms or adjust the research filters."
        return {"answer": answer}

    def _generate_followups(self, state: ResearchState) -> dict[str, object]:
        if state.get("validation_issue") or state["search_plan"].intent == "unsupported":
            return {"suggestions": []}
        if state.get("context_type") == "authors" and state.get("authors"):
            names = [
                str(author.get("name", "")) for author in state["authors"] if author.get("name")
            ]
            if len(names) == 1:
                name = names[0]
                suggestions = [
                    f"Show the most cited papers by {name}",
                    f"Show the newest papers by {name}",
                    f"Find all papers by {name}",
                ]
            else:
                suggestions = [
                    "Compare these researcher profiles",
                    "Which researcher has the highest h-index?",
                    "Summarize each researcher's main topics",
                ]
        elif state.get("results"):
            suggestions = [
                "Show me more papers",
                "Give me BibTeX code for these papers",
                "Give me RIS code for these papers",
                "Draft a concise state-of-the-art synthesis from these papers",
                "Compare the main methods and findings across these papers",
                "Give me an overview of the authors represented here",
            ]
        else:
            suggestions = []
        return {"suggestions": suggestions}


def _is_more_results_request(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    return bool(
        re.search(
            r"\b(more|additional|other|further)\b.*\b(papers?|publications?|studies|research)\b",
            normalized,
        )
        or re.search(r"\b(find|search|show|get)\b.*\bmore\b", normalized)
    )


def _context_followup_plan(message: str, state: ResearchState) -> SearchPlan | None:
    """Resolve unambiguous follow-ups without another planning or retrieval call."""
    if not state.get("results"):
        return None
    if _is_more_results_request(message):
        return SearchPlan(intent="more_results")
    if re.search(r"\bbibtex\b|\bris(?:\s+code)?\b", message, re.IGNORECASE) or _reference_style(
        message
    ):
        return SearchPlan(intent="bibliography")
    if _is_author_profile_request(message):
        return SearchPlan(intent="author_overview")
    if _is_revision_request(message) or _is_current_results_request(message):
        return SearchPlan(intent="result_analysis")
    return None


def _broader_review_query(query: str) -> str | None:
    broader = re.sub(
        r"\b(?:systematic|scoping|literature|narrative|umbrella)\s+reviews?\b|\breview papers?\b",
        "",
        query,
        flags=re.IGNORECASE,
    )
    broader = " ".join(broader.split()).strip(" ,;:-")
    return broader if broader and broader.casefold() != query.strip().casefold() else None


def _is_current_results_request(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    reference_terms = (
        r"apa|mla|ieee|chicago|harvard|vancouver|bibtex|ris|references?|bibliography|cite|citation"
    )
    analysis_terms = (
        r"summari[sz]e|compare|synthesis|state[- ]of[- ]the[- ]art|literature review|"
        r"methods?|findings?|research gaps?|author overview|overview of the authors?"
    )
    current_terms = r"these|those|current|above|the papers?|the publications?|the references?"
    return bool(
        re.search(rf"\b({reference_terms})\b", normalized)
        or re.search(rf"\b({analysis_terms})\b.*\b({current_terms})\b", normalized)
        or re.search(rf"\b({current_terms})\b.*\b({analysis_terms})\b", normalized)
    )


def _is_revision_request(message: str) -> bool:
    normalized = " ".join(message.casefold().split()).strip(" .!?")
    return bool(
        re.search(
            r"^(?:please\s+)?(?:make|write|rewrite|expand|shorten|condense|revise|continue|"
            r"elaborate)(?:\s+(?:it|this|that|the answer|the section|the text))?\b",
            normalized,
        )
        or re.fullmatch(
            r"(?:a\s+)?(?:little\s+|bit\s+|much\s+)?(?:longer|shorter|more detailed|"
            r"more concise|more formal|more academic|clearer)",
            normalized,
        )
    )


def _is_author_profile_request(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    return bool(
        re.search(r"\b(h[- ]?index|i10|orcid|(?:author|researcher) profiles?)\b", normalized)
        or re.search(
            r"\b(tell me about|overview of|information about)\b.*\b(authors?|researchers?)\b",
            normalized,
        )
        or re.search(r"\bcompare\b.*\b(authors?|researchers?)\b", normalized)
    )


def _author_names_from_results(results: list[dict[str, object]]) -> list[str]:
    names: list[str] = []
    for result in results:
        authors = result.get("authors")
        if not isinstance(authors, list):
            continue
        for author in authors:
            if isinstance(author, str) and author not in names:
                names.append(author)
    return names[:5]


def _work_id_for_request(state: ResearchState) -> str:
    explicit = state["search_plan"].work_id
    if explicit:
        return explicit
    results = _filter_results_by_selection(
        state.get("results", []), state.get("included_result_ids", [])
    )
    citation = re.search(r"\[(\d+)]", state["message"])
    index = int(citation.group(1)) - 1 if citation else 0
    if 0 <= index < len(results):
        identifier = results[index].get("id")
        return identifier if isinstance(identifier, str) else ""
    return ""


def _publication_state(results: list[ResearchResult]) -> dict[str, object]:
    return {
        "results": [result.model_dump(mode="json", by_alias=True) for result in results],
        "context_type": "papers",
    }


def _considered_results(state: ResearchState) -> list[dict[str, object]]:
    results = state.get("results", [])
    included_ids = state.get("included_result_ids", [])
    if state.get("route") not in {"reuse", "authors"} or not included_ids:
        return results
    return _filter_results_by_selection(results, included_ids)


def _filter_results_by_selection(
    results: list[dict[str, object]], included_ids: list[str]
) -> list[dict[str, object]]:
    if not included_ids:
        return results
    included = set(included_ids)
    return [result for result in results if str(result.get("id", "")) in included]


def _has_abstract(result: Mapping[str, object]) -> bool:
    summary = str(result.get("summary", "")).strip()
    return bool(summary and summary != "No abstract is available for this publication.")


def _format_metadata_only_analysis(results: list[dict[str, object]]) -> str:
    lines = [
        (
            "The available publication metadata supports a thematic overview, but not a reliable "
            "synthesis of methods, findings, study locations, or conclusions because these papers "
            "do not include abstracts."
        ),
        "",
    ]
    for index, result in enumerate(results, start=1):
        title = str(result.get("title", "Untitled"))
        topics = result.get("topics", [])
        topic_text = ", ".join(str(topic) for topic in topics) if isinstance(topics, list) else ""
        suffix = f" — indexed topics: {topic_text}" if topic_text else ""
        lines.append(f"- [{index}] {title}{suffix}")
    lines.extend(
        [
            "",
            (
                "Abstracts or full text are needed before making paper-specific claims about what "
                "these publications found or argued."
            ),
        ]
    )
    return "\n".join(lines)


def _format_bibtex(results: list[dict[str, object]]) -> str:
    entries: list[str] = []
    used_keys: set[str] = set()
    for index, result in enumerate(results, start=1):
        authors = [str(author) for author in result.get("authors", [])]
        surname = re.sub(r"[^a-zA-Z0-9]", "", authors[0].split()[-1]) if authors else "work"
        year = str(result.get("year", "n.d."))
        key = f"{surname.lower()}{year}"
        if key in used_keys:
            key = f"{key}{index}"
        used_keys.add(key)
        fields = [
            f"  title = {{{_bibtex_escape(str(result.get('title', 'Untitled')))}}}",
            f"  author = {{{' and '.join(_bibtex_escape(author) for author in authors)}}}",
            f"  year = {{{year}}}",
        ]
        source = str(result.get("source", "")).strip()
        if source and source != "Unknown source":
            fields.append(f"  journal = {{{_bibtex_escape(source)}}}")
        raw_doi = result.get("doi")
        doi = str(raw_doi).strip() if raw_doi else ""
        if doi:
            fields.append(f"  doi = {{{doi.removeprefix('https://doi.org/')}}}")
        entries.append(f"@article{{{key},\n" + ",\n".join(fields) + "\n}")
    return "```bibtex\n" + "\n\n".join(entries) + "\n```"


def _format_ris(results: list[dict[str, object]]) -> str:
    records: list[str] = []
    for result in results:
        lines = ["TY  - JOUR", f"TI  - {result.get('title', 'Untitled')}"]
        lines.extend(f"AU  - {author}" for author in result.get("authors", []))
        lines.append(f"PY  - {result.get('year', '')}")
        source = str(result.get("source", "")).strip()
        if source and source != "Unknown source":
            lines.append(f"JO  - {source}")
        raw_doi = result.get("doi")
        doi = str(raw_doi).strip() if raw_doi else ""
        if doi:
            lines.append(f"DO  - {doi.removeprefix('https://doi.org/')}")
        lines.append("ER  -")
        records.append("\n".join(lines))
    return "```ris\n" + "\n\n".join(records) + "\n```"


def _reference_style(message: str) -> str | None:
    normalized = " ".join(message.casefold().split())
    styles = {
        "apa 7": "APA 7",
        "apa": "APA 7",
        "mla 9": "MLA 9",
        "mla": "MLA 9",
        "ieee": "IEEE",
        "chicago": "Chicago",
        "harvard": "Harvard",
        "vancouver": "Vancouver",
    }
    return next((label for term, label in styles.items() if term in normalized), None)


def _format_references(results: list[dict[str, object]], style: str) -> str:
    references = [
        f"[{index}] {_format_reference(result, style)}"
        for index, result in enumerate(results, start=1)
    ]
    return f"### {style} references\n\n" + "\n\n".join(references)


def _format_reference(result: dict[str, object], style: str) -> str:
    raw_authors = result.get("authors", [])
    authors = (
        [str(author).strip() for author in raw_authors if str(author).strip()]
        if isinstance(raw_authors, list)
        else []
    )
    author_text = ", ".join(authors) if authors else "Unknown author"
    title = str(result.get("title", "Untitled")).strip() or "Untitled"
    source = str(result.get("source", "")).strip()
    year = str(result.get("year", "n.d."))
    raw_doi = result.get("doi")
    doi = str(raw_doi).strip() if raw_doi else ""
    doi_suffix = f" {doi}" if doi else ""
    source_italic = f" *{source}*." if source and source != "Unknown source" else ""

    if style == "APA 7":
        return f"{author_text}. ({year}). {title}.{source_italic}{doi_suffix}".strip()
    if style == "MLA 9":
        source_part = f" *{source}*," if source and source != "Unknown source" else ""
        return f"{author_text}. “{title}.”{source_part} {year}.{doi_suffix}".strip()
    if style == "Chicago":
        return f"{author_text}. “{title}.”{source_italic} {year}.{doi_suffix}".strip()
    if style == "Harvard":
        return f"{author_text} ({year}) ‘{title}’.{source_italic}{doi_suffix}".strip()
    if style == "Vancouver":
        source_part = f" {source}." if source and source != "Unknown source" else ""
        return f"{author_text}. {title}.{source_part} {year}.{doi_suffix}".strip()
    source_part = f" *{source}*," if source and source != "Unknown source" else ""
    return f"{author_text}, “{title},”{source_part} {year}.{doi_suffix}".strip()


def _bibtex_escape(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("&", "\\&")
    )
