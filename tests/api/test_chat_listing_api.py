import typing
import uuid

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, username: str) -> int:
    response = await client.post(
        "/api/auth/register/",
        json={"username": username, "password": "hunter2hunter2", "display_name": username.title()},
    )
    user_id: typing.Final = response.json()["id"]
    return user_id


async def _login(client: AsyncClient, username: str) -> None:
    await client.post("/api/auth/login/", json={"username": username, "password": "hunter2hunter2"})


async def _create_direct_chat(client: AsyncClient) -> tuple[int, int]:
    """Register bob then alice (alice ends up holding the cookie/actor) and open a direct chat."""
    bob_id = await _register(client, "bob")
    await _register(client, "alice")
    chat_id: typing.Final = (
        await client.post("/api/chats/", json={"chat_type": "direct", "member_ids": [bob_id]})
    ).json()["id"]
    return chat_id, bob_id


async def _send(client: AsyncClient, chat_id: int, text: str) -> dict[str, typing.Any]:
    response = await client.post(
        f"/api/chats/{chat_id}/messages/",
        json={"idempotency_key": str(uuid.uuid4()), "text": text},
    )
    return response.json()


@pytest.mark.usefixtures("db_session")
async def test_listing_returns_only_the_callers_chats(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _register(client, "mallory")  # mallory is not a member of any chat

    mallory_response = await client.get("/api/chats/")
    await _login(client, "alice")
    alice_response = await client.get("/api/chats/")

    assert mallory_response.json()["items"] == []
    assert [item["id"] for item in alice_response.json()["items"]] == [chat_id]


@pytest.mark.usefixtures("db_session")
async def test_listing_populates_unread_count_and_last_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _login(client, "bob")
    first = await _send(client, chat_id, "one")
    await _send(client, chat_id, "two")
    await _login(client, "alice")

    response = await client.get("/api/chats/")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["unread_count"] == 2
    assert item["last_message"]["id"] != first["id"]
    assert item["last_message"]["text"] == "two"


@pytest.mark.usefixtures("db_session")
async def test_chat_with_no_messages_has_null_last_message_and_zero_unread(client: AsyncClient) -> None:
    await _create_direct_chat(client)

    response = await client.get("/api/chats/")

    item = response.json()["items"][0]
    assert item["last_message"] is None
    assert item["unread_count"] == 0


@pytest.mark.usefixtures("db_session")
async def test_mark_read_by_non_member_is_forbidden(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _register(client, "mallory")

    response = await client.post(f"/api/chats/{chat_id}/read/", json={"last_read_message_id": 1})

    assert response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_mark_read_clears_unread_count(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _login(client, "bob")
    message = await _send(client, chat_id, "one")
    await _login(client, "alice")

    read_response = await client.post(f"/api/chats/{chat_id}/read/", json={"last_read_message_id": message["id"]})
    listing = await client.get("/api/chats/")

    assert read_response.status_code == 200
    assert read_response.json()["last_read_message_id"] == message["id"]
    assert listing.json()["items"][0]["unread_count"] == 0


@pytest.mark.usefixtures("db_session")
async def test_marking_read_with_a_lower_id_leaves_the_marker_unchanged(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _login(client, "bob")
    first = await _send(client, chat_id, "one")
    second = await _send(client, chat_id, "two")
    await _login(client, "alice")
    await client.post(f"/api/chats/{chat_id}/read/", json={"last_read_message_id": second["id"]})

    response = await client.post(f"/api/chats/{chat_id}/read/", json={"last_read_message_id": first["id"]})

    assert response.status_code == 200
    assert response.json()["last_read_message_id"] == second["id"]


@pytest.mark.usefixtures("db_session")
async def test_mark_read_rejects_a_message_id_from_a_different_chat(client: AsyncClient) -> None:
    chat_id, bob_id = await _create_direct_chat(client)
    other_message = await _send(client, chat_id, "in the direct chat")
    carol_id = await _register(client, "carol")
    await _login(client, "alice")
    group_chat_id = (
        await client.post("/api/chats/", json={"chat_type": "group", "member_ids": [bob_id, carol_id], "title": "g"})
    ).json()["id"]

    response = await client.post(
        f"/api/chats/{group_chat_id}/read/", json={"last_read_message_id": other_message["id"]}
    )

    assert response.status_code == 400


async def test_list_chats_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/chats/")
    assert response.status_code == 401


async def test_mark_read_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/chats/1/read/", json={"last_read_message_id": 1})
    assert response.status_code == 401
