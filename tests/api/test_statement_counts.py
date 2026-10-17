import typing
import uuid

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tests.api.helpers import count_statements, create_direct_chat, login, register, send


async def _measure(session: AsyncSession, request: typing.Awaitable[Response]) -> tuple[Response, list[str]]:
    with count_statements(session) as statements:
        response: typing.Final = await request
    return response, [statement for statement in statements if "SAVEPOINT" not in statement]


async def test_register_runs_one_statement(client: AsyncClient, db_session: AsyncSession) -> None:
    response, statements = await _measure(
        db_session,
        client.post("/api/auth/register/", json={"username": "zed", "password": "hunter2hunter2", "display_name": "Z"}),
    )

    assert response.status_code == 201
    assert len(statements) == 1, statements


async def test_logout_runs_three_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    await register(client, "alice")

    response, statements = await _measure(db_session, client.post("/api/auth/logout/"))

    assert response.status_code == 204
    assert len(statements) == 3, statements


async def test_new_direct_chat_runs_three_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    bob_id: typing.Final = await register(client, "bob")
    await register(client, "alice")

    response, statements = await _measure(
        db_session, client.post("/api/chats/", json={"chat_type": "direct", "member_ids": [bob_id]})
    )

    assert response.status_code == 201
    assert {member["user_id"] for member in response.json()["members"]} == {bob_id, response.json()["created_by_id"]}
    assert len(statements) == 3, statements


async def test_direct_chat_replay_runs_three_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    _, bob_id = await create_direct_chat(client)

    response, statements = await _measure(
        db_session, client.post("/api/chats/", json={"chat_type": "direct", "member_ids": [bob_id]})
    )

    assert response.status_code == 200
    assert len(response.json()["members"]) == 2
    assert len(statements) == 3, statements


async def test_new_group_chat_runs_three_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    member_ids: typing.Final = [await register(client, "bob"), await register(client, "carol")]
    await register(client, "alice")

    response, statements = await _measure(
        db_session, client.post("/api/chats/", json={"chat_type": "group", "title": "g", "member_ids": member_ids})
    )

    assert response.status_code == 201
    assert response.json()["title"] == "g"
    assert len(response.json()["members"]) == 3
    assert len(statements) == 3, statements


async def test_chat_listing_runs_two_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)
    await send(client, chat_id, "hello")

    response, statements = await _measure(db_session, client.get("/api/chats/"))

    assert response.json()["items"][0]["last_message"]["text"] == "hello"
    assert len(statements) == 2, statements


async def test_chat_detail_runs_two_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)

    response, statements = await _measure(db_session, client.get(f"/api/chats/{chat_id}/"))

    assert response.status_code == 200
    assert len(response.json()["members"]) == 2
    assert len(statements) == 2, statements


async def test_mark_read_runs_three_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)
    message: typing.Final = await send(client, chat_id, "hello")
    await login(client, "bob")

    response, statements = await _measure(
        db_session, client.post(f"/api/chats/{chat_id}/read/", json={"last_read_message_id": message["id"]})
    )

    assert response.json()["last_read_message_id"] == message["id"]
    assert len(statements) == 3, statements


async def test_new_message_runs_four_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)

    response, statements = await _measure(
        db_session,
        client.post(f"/api/chats/{chat_id}/messages/", json={"idempotency_key": str(uuid.uuid4()), "text": "hi"}),
    )

    assert response.status_code == 201
    assert len(statements) == 4, statements


async def test_edit_runs_three_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)
    message: typing.Final = await send(client, chat_id, "hi")

    response, statements = await _measure(
        db_session, client.patch(f"/api/messages/{message['id']}/", json={"text": "fixed"})
    )

    assert response.json()["text"] == "fixed"
    assert len(statements) == 3, statements


async def test_delete_of_an_older_message_runs_four_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)
    older: typing.Final = await send(client, chat_id, "one")
    await send(client, chat_id, "two")

    response, statements = await _measure(db_session, client.delete(f"/api/messages/{older['id']}/"))

    assert response.status_code == 204
    assert len(statements) == 4, statements


async def test_delete_of_the_last_message_runs_four_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)
    await send(client, chat_id, "one")
    last: typing.Final = await send(client, chat_id, "two")

    response, statements = await _measure(db_session, client.delete(f"/api/messages/{last['id']}/"))

    assert response.status_code == 204
    assert len(statements) == 4, statements


async def test_repeated_delete_runs_two_statements(client: AsyncClient, db_session: AsyncSession) -> None:
    chat_id, _ = await create_direct_chat(client)
    message: typing.Final = await send(client, chat_id, "one")
    await client.delete(f"/api/messages/{message['id']}/")

    response, statements = await _measure(db_session, client.delete(f"/api/messages/{message['id']}/"))

    assert response.status_code == 204
    assert len(statements) == 2, statements
