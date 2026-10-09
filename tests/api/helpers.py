import contextlib
import typing
import uuid
from collections.abc import Generator

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


async def register(client: AsyncClient, username: str) -> int:
    response = await client.post(
        "/api/auth/register/",
        json={"username": username, "password": "hunter2hunter2", "display_name": username.title()},
    )
    user_id: typing.Final = response.json()["id"]
    return user_id


async def login(client: AsyncClient, username: str) -> None:
    await client.post("/api/auth/login/", json={"username": username, "password": "hunter2hunter2"})


async def create_direct_chat(client: AsyncClient) -> tuple[int, int]:
    """Register bob then alice (alice ends up holding the cookie/actor) and open a direct chat."""
    bob_id = await register(client, "bob")
    await register(client, "alice")
    chat_id: typing.Final = (
        await client.post("/api/chats/", json={"chat_type": "direct", "member_ids": [bob_id]})
    ).json()["id"]
    return chat_id, bob_id


async def send(client: AsyncClient, chat_id: int, text: str, key: uuid.UUID | None = None) -> dict[str, typing.Any]:
    response = await client.post(
        f"/api/chats/{chat_id}/messages/",
        json={"idempotency_key": str(key or uuid.uuid4()), "text": text},
    )
    return response.json()


@contextlib.contextmanager
def count_statements(session: AsyncSession) -> Generator[list[str]]:
    """Collect every SQL statement sent on the test connection behind ``session`` while the block runs."""
    connection: typing.Final = session.bind
    assert isinstance(connection, AsyncConnection)
    statements: typing.Final[list[str]] = []

    def record(_conn: sa.Connection, _cursor: object, statement: str, *_: object) -> None:
        statements.append(statement)

    event.listen(connection.sync_connection, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record)
