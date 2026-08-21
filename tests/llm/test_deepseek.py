from typing import Any

import pytest

from app.llm.deepseek import DeepSeekError, DeepSeekLLM, build_research_prompt


class FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content: str | None) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content: str | None = "A grounded answer [1].") -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> FakeCompletion:
        self.calls.append(kwargs)
        return FakeCompletion(self.content)


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = FakeChat(completions)


@pytest.mark.asyncio
async def test_deepseek_generates_an_answer_with_the_configured_model() -> None:
    completions = FakeCompletions()
    llm = DeepSeekLLM(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=FakeClient(completions),
    )

    answer = await llm.generate_answer(
        "How does sleep affect memory?",
        [{"title": "Sleep and Memory", "year": 2024}],
    )

    assert answer == "A grounded answer [1]."
    request = completions.calls[0]
    assert request["model"] == "deepseek-v4-flash"
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}
    system_prompt = request["messages"][0]["content"]
    assert "Never mention supplied or provided evidence" in system_prompt
    assert "publication cards are shown below" in system_prompt
    assert "Do not recommend other databases" in system_prompt
    assert "Sleep and Memory" in request["messages"][1]["content"]
    assert "How does sleep affect memory?" in request["messages"][1]["content"]
    assert request["max_tokens"] == 1_400


@pytest.mark.asyncio
async def test_deepseek_allows_complete_bibliography_outputs() -> None:
    completions = FakeCompletions("[1] A complete reference.")
    llm = DeepSeekLLM(api_key="test-key", client=FakeClient(completions))

    await llm.generate_answer(
        "Format these references in IEEE",
        [{"title": f"Paper {index}", "year": 2024} for index in range(10)],
    )

    assert completions.calls[0]["max_tokens"] == 3_200


@pytest.mark.asyncio
async def test_deepseek_allows_long_revision_outputs() -> None:
    completions = FakeCompletions("A longer section.")
    llm = DeepSeekLLM(api_key="test-key", client=FakeClient(completions))

    await llm.generate_answer(
        "Previous response:\nA short section.\n\nFollow-up instruction:\nmake it longer",
        [{"title": "Paper", "year": 2024}],
    )

    assert completions.calls[0]["max_tokens"] == 3_000


@pytest.mark.asyncio
async def test_deepseek_rejects_an_empty_response() -> None:
    llm = DeepSeekLLM(api_key="test-key", client=FakeClient(FakeCompletions("  ")))

    with pytest.raises(DeepSeekError, match="empty answer"):
        await llm.generate_answer("A question", [])


@pytest.mark.asyncio
async def test_deepseek_extracts_a_structured_author_search_plan() -> None:
    completions = FakeCompletions(
        '{"query":"","author":"Anass Yarroudh","intent":"author_publications"}'
    )
    llm = DeepSeekLLM(api_key="test-key", client=FakeClient(completions))

    plan = await llm.interpret_search(
        "Can you find all papers of author called Anass Yarroudh"
    )

    assert plan.author == "Anass Yarroudh"
    assert plan.query == ""
    assert plan.intent == "author_publications"
    request = completions.calls[0]
    assert request["response_format"] == {"type": "json_object"}
    assert "valid JSON" in request["messages"][0]["content"]


@pytest.mark.asyncio
async def test_deepseek_rejects_an_invalid_search_plan() -> None:
    llm = DeepSeekLLM(api_key="test-key", client=FakeClient(FakeCompletions("not json")))

    with pytest.raises(DeepSeekError, match="invalid search plan"):
        await llm.interpret_search("Find recent research")


def test_prompt_requires_grounding_and_citations() -> None:
    prompt = build_research_prompt("A question", [{"title": "A source"}])

    assert "Do not invent findings or citations" in prompt
    assert "Do not describe how the publications were" in prompt
    assert "obtained or refer to them as evidence" in prompt
    assert "Available evidence" not in prompt
    assert "[1]" in prompt
    assert "A source" in prompt
