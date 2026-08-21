import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import asyncpg


class HistoryRepository(Protocol):
    async def initialize(self) -> None: ...

    async def close(self) -> None: ...

    async def save_turn(
        self, conversation_id: str, query: str, payload: Mapping[str, Any]
    ) -> None: ...

    async def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]: ...

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None: ...

    async def latest_context(self, conversation_id: str) -> dict[str, Any] | None: ...

    async def delete_conversation(self, conversation_id: str) -> bool: ...


class NullHistoryRepository:
    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def save_turn(self, conversation_id: str, query: str, payload: Mapping[str, Any]) -> None:
        return None

    async def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        return []

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        return None

    async def latest_context(self, conversation_id: str) -> dict[str, Any] | None:
        return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        return False


class InMemoryHistoryRepository(NullHistoryRepository):
    def __init__(self) -> None:
        self._conversations: dict[str, dict[str, Any]] = {}

    async def save_turn(self, conversation_id: str, query: str, payload: Mapping[str, Any]) -> None:
        now = datetime.now(UTC)
        conversation = self._conversations.setdefault(
            conversation_id,
            {
                "id": conversation_id,
                "title": _conversation_title(query),
                "createdAt": now,
                "updatedAt": now,
                "turns": [],
            },
        )
        conversation["updatedAt"] = now
        conversation["turns"].append(
            {"id": str(uuid4()), "query": query, **dict(payload), "createdAt": now}
        )

    async def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        ordered = sorted(
            self._conversations.values(), key=lambda item: item["updatedAt"], reverse=True
        )
        return [
            {key: value for key, value in item.items() if key != "turns"}
            for item in ordered[:limit]
        ]

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        return self._conversations.get(conversation_id)

    async def latest_context(self, conversation_id: str) -> dict[str, Any] | None:
        conversation = self._conversations.get(conversation_id)
        if not conversation or not conversation["turns"]:
            return None
        return conversation["turns"][-1]

    async def delete_conversation(self, conversation_id: str) -> bool:
        return self._conversations.pop(conversation_id, None) is not None


class PostgresHistoryRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=10)
        async with self._pool.acquire() as connection:
            await connection.execute(_SCHEMA)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def save_turn(self, conversation_id: str, query: str, payload: Mapping[str, Any]) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                INSERT INTO conversations (id, title)
                VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
                """,
                conversation_id,
                _conversation_title(query),
            )
            await connection.execute(
                """
                INSERT INTO conversation_turns (id, conversation_id, query, payload)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                str(uuid4()),
                conversation_id,
                query,
                json.dumps(dict(payload), default=str),
            )

    async def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self._require_pool().fetch(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [_conversation_row(row) for row in rows]

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        pool = self._require_pool()
        conversation = await pool.fetchrow(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = $1",
            conversation_id,
        )
        if conversation is None:
            return None
        turns = await pool.fetch(
            """
            SELECT id, query, payload, created_at
            FROM conversation_turns
            WHERE conversation_id = $1
            ORDER BY created_at, id
            """,
            conversation_id,
        )
        result = _conversation_row(conversation)
        result["turns"] = [_turn_row(row) for row in turns]
        return result

    async def latest_context(self, conversation_id: str) -> dict[str, Any] | None:
        row = await self._require_pool().fetchrow(
            """
            SELECT id, query, payload, created_at
            FROM conversation_turns
            WHERE conversation_id = $1
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            conversation_id,
        )
        return _turn_row(row) if row is not None else None

    async def delete_conversation(self, conversation_id: str) -> bool:
        result = await self._require_pool().execute(
            "DELETE FROM conversations WHERE id = $1", conversation_id
        )
        return result == "DELETE 1"

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("History repository has not been initialized")
        return self._pool


def _conversation_title(query: str) -> str:
    compact = " ".join(query.split())
    return compact[:77] + "..." if len(compact) > 80 else compact


def _conversation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _turn_row(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "id": str(row["id"]),
        "query": row["query"],
        **dict(payload),
        "createdAt": row["created_at"],
    }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversation_turns_conversation_created_idx
    ON conversation_turns (conversation_id, created_at);
"""
