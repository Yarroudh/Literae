import re
from typing import Literal, Protocol

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.query_understanding import QueryInterpreter, merge_search_plan
from app.agent.state import ResearchState
from app.api.schemas import AuthorResult, ResearchFilters, ResearchResult
from app.debugging.laminar import trace_span, traced_node
from app.llm.deepseek import AnswerGenerator
from app.retrieval.openalex import ResearchSearcher


class ResearchWorkflow(Protocol):
    async def run(
        self,
        *,
        conversation_id: str,
        message: str,
        filters: ResearchFilters,
    ) -> tuple[str, list[ResearchResult], bool, list[AuthorResult], bool, str | None, list[str]]: ...


class LangGraphResearchWorkflow:
    def __init__(
        self,
        *,
        query_interpreter: QueryInterpreter,
        research_searcher: ResearchSearcher,
        answer_generator: AnswerGenerator,
    ) -> None:
        self._query_interpreter = query_interpreter
        self._research_searcher = research_searcher
        self._answer_generator = answer_generator
        builder = StateGraph(ResearchState)
        builder.add_node("interpret_request", traced_node("interpret_request", self._interpret_request))
        builder.add_node("resolve_context", traced_node("resolve_context", self._resolve_context))
        builder.add_node("validate_search_plan", traced_node("validate_search_plan", self._validate_search_plan))
        builder.add_node("route_request", traced_node("route_request", self._route_request))
        builder.add_node("search_publications", traced_node("search_publications", self._search_publications))
        builder.add_node("search_authors", traced_node("search_authors", self._search_authors))
        builder.add_node("select_evidence", traced_node("select_evidence", self._select_evidence))
        builder.add_node("execute_research_action", traced_node("execute_research_action", self._execute_research_action))
        builder.add_node("verify_answer", traced_node("verify_answer", self._verify_answer))
        builder.add_node("recover_or_clarify", traced_node("recover_or_clarify", self._recover_or_clarify))
        builder.add_node("generate_followups", traced_node("generate_followups", self._generate_followups))
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
                "reuse": "select_evidence",
                "recover": "recover_or_clarify",
            },
        )
        builder.add_edge("search_publications", "select_evidence")
        builder.add_edge("search_authors", "select_evidence")
        builder.add_edge("select_evidence", "execute_research_action")
        builder.add_conditional_edges("execute_research_action", self._after_action, {"verify": "verify_answer", "recover": "recover_or_clarify"})
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
    ) -> tuple[str, list[ResearchResult], bool, list[AuthorResult], bool, str | None, list[str]]:
        with trace_span(
            "literae_research_request",
            input_data={"conversation_id": conversation_id, "message": message},
            session_id=conversation_id,
        ):
            state = await self._graph.ainvoke(
                {"message": message, "explicit_filters": filters},
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
        plan = await self._query_interpreter.interpret_search(state["message"])
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
        if has_papers and (_is_current_results_request(message) or _is_revision_request(message) or state["search_plan"].intent in {"bibliography", "result_analysis", "author_overview"}):
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
            _is_current_results_request(message) or _is_revision_request(message) or plan.intent in reusable_intents)
        wants_authors = plan.intent == "author_overview" or _is_author_profile_request(message)
        reuses_current_authors = bool(state.get("authors")) and not plan.authors and not plan.author
        if plan.intent == "unsupported":
            route = "recover"
        elif wants_authors:
            route = "authors"
        elif should_reuse and not _is_more_results_request(message):
            route = "reuse"
        else:
            route = "search"
        return {
            "route": route,
            "show_results": route == "search",
            "show_authors": route == "authors" and not reuses_current_authors,
        }

    def _next_step(self, state: ResearchState) -> Literal["search", "authors", "reuse", "recover"]:
        if state.get("validation_issue"):
            return "recover"
        if state["route"] == "recover":
            return "recover"
        if state["route"] == "authors":
            return "authors"
        return "reuse" if state["route"] == "reuse" else "search"

    async def _search_publications(self, state: ResearchState) -> dict[str, object]:
        results = await self._research_searcher.search(
            state["search_query"], state["search_filters"], page=state.get("page", 1)
        )
        return {
            "results": [result.model_dump(mode="json", by_alias=True) for result in results],
            "context_type": "papers",
        }

    async def _search_authors(self, state: ResearchState) -> dict[str, object]:
        plan = state["search_plan"]
        names = plan.authors or ([plan.author] if plan.author else [])
        if not names:
            names = _author_names_from_results(state.get("results", []))
        if not names and state.get("authors"):
            return {}
        authors = await self._research_searcher.search_authors(names)
        return {
            "authors": [author.model_dump(mode="json", by_alias=True) for author in authors],
            "context_type": "authors",
        }

    def _select_evidence(self, state: ResearchState) -> dict[str, object]:
        # Keep prompts bounded while preserving enough material for comparisons.
        return {"selected_results": state.get("results", [])[:12]}

    async def _execute_research_action(self, state: ResearchState) -> dict[str, object]:
        if state.get("validation_issue"):
            return {"action": "recover"}
        if state.get("route") == "search" and not state.get("results"):
            return {"action": "recover"}
        if state.get("route") == "authors" and not state.get("authors"):
            return {"action": "recover"}
        message = state["message"]
        if re.search(r"\bbibtex\b", message, re.IGNORECASE):
            return {"answer": _format_bibtex(state.get("selected_results", [])), "action": "verify"}
        if re.search(r"\bris\b", message, re.IGNORECASE):
            return {"answer": _format_ris(state.get("selected_results", [])), "action": "verify"}
        if state.get("route") == "authors":
            answer = await self._answer_generator.generate_author_answer(
                state["message"], state.get("authors", [])
            )
            return {"answer": answer, "action": "verify"}
        results = state.get("selected_results", [])
        question = state["message"]
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
            answer = re.sub(r"\[(\d+)\]", lambda match: match.group(0) if int(match.group(1)) <= count else "", answer)
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
            answer = "I couldn't identify a matching researcher. Try adding an affiliation or ORCID."
        else:
            answer = "I couldn't find closely related publications. Try broader terms or adjust the research filters."
        return {"answer": answer}

    def _generate_followups(self, state: ResearchState) -> dict[str, object]:
        if state.get("validation_issue") or state["search_plan"].intent == "unsupported":
            return {"suggestions": []}
        if state.get("context_type") == "authors" and state.get("authors"):
            names = [str(author.get("name", "")) for author in state["authors"] if author.get("name")]
            if len(names) == 1:
                name = names[0]
                suggestions = [f"Show the most cited papers by {name}", f"Show the newest papers by {name}", f"Find all papers by {name}"]
            else:
                suggestions = ["Compare these researcher profiles", "Which researcher has the highest h-index?", "Summarize each researcher's main topics"]
        elif state.get("results"):
            suggestions = ["Give me BibTeX code for these papers", "Give me RIS code for these papers", "Draft a concise state-of-the-art synthesis from these papers", "Compare the main methods and findings across these papers", "Give me an overview of the authors represented here"]
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
        or re.search(r"\b(tell me about|overview of|information about)\b.*\b(authors?|researchers?)\b", normalized)
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
        doi = str(result.get("doi", "")).strip()
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
        doi = str(result.get("doi", "")).strip()
        if doi:
            lines.append(f"DO  - {doi.removeprefix('https://doi.org/')}")
        lines.append("ER  -")
        records.append("\n".join(lines))
    return "```ris\n" + "\n\n".join(records) + "\n```"


def _bibtex_escape(value: str) -> str:
    return value.replace("\\", "\\textbackslash{}") .replace("{", "\\{").replace("}", "\\}").replace("&", "\\&")
