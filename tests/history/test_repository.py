import pytest

from app.history.repository import InMemoryHistoryRepository


@pytest.mark.asyncio
async def test_in_memory_history_saves_lists_loads_and_deletes_conversations() -> None:
    history = InMemoryHistoryRepository()
    await history.save_turn(
        "conversation-1",
        "Find papers about sleep",
        {"answer": "Found one.", "results": [], "authors": []},
    )

    summaries = await history.list_conversations()
    conversation = await history.get_conversation("conversation-1")
    latest = await history.latest_context("conversation-1")

    assert summaries[0]["title"] == "Find papers about sleep"
    assert conversation is not None and conversation["turns"][0]["answer"] == "Found one."
    assert latest is not None and latest["query"] == "Find papers about sleep"
    assert await history.delete_conversation("conversation-1") is True
    assert await history.get_conversation("conversation-1") is None
