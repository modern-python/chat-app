import uuid

import pytest
from httpx import AsyncClient

from app.use_cases.fetch_messages import MAX_PAGE_SIZE
from tests.api.helpers import create_direct_chat as _create_direct_chat
from tests.api.helpers import register as _register
from tests.api.helpers import send as _send


@pytest.mark.usefixtures("db_session")
async def test_send_message_returns_201(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    response = await client.post(
        f"/api/chats/{chat_id}/messages/",
        json={"idempotency_key": str(uuid.uuid4()), "text": "hi"},
    )
    assert response.status_code == 201
    assert response.json()["text"] == "hi"


@pytest.mark.usefixtures("db_session")
async def test_resending_the_same_key_returns_200_with_the_same_id(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    key = uuid.uuid4()
    first = await client.post(f"/api/chats/{chat_id}/messages/", json={"idempotency_key": str(key), "text": "hi"})
    second = await client.post(
        f"/api/chats/{chat_id}/messages/", json={"idempotency_key": str(key), "text": "hi again"}
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.usefixtures("db_session")
async def test_before_id_returns_newest_first_and_excludes_the_cursor_row(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    first = await _send(client, chat_id, "one")
    second = await _send(client, chat_id, "two")
    third = await _send(client, chat_id, "three")

    response = await client.get(f"/api/chats/{chat_id}/messages/", params={"before_id": third["id"]})

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [second["id"], first["id"]]


@pytest.mark.usefixtures("db_session")
async def test_after_id_returns_oldest_first_and_excludes_the_cursor_row(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    first = await _send(client, chat_id, "one")
    second = await _send(client, chat_id, "two")
    third = await _send(client, chat_id, "three")

    response = await client.get(f"/api/chats/{chat_id}/messages/", params={"after_id": first["id"]})

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [second["id"], third["id"]]


@pytest.mark.usefixtures("db_session")
async def test_non_member_is_rejected_on_send_and_list(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _register(client, "mallory")

    send_response = await client.post(
        f"/api/chats/{chat_id}/messages/", json={"idempotency_key": str(uuid.uuid4()), "text": "hi"}
    )
    list_response = await client.get(f"/api/chats/{chat_id}/messages/")

    assert send_response.status_code == 403
    assert list_response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_both_cursors_together_are_rejected(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _send(client, chat_id, "one")

    response = await client.get(f"/api/chats/{chat_id}/messages/", params={"before_id": 1, "after_id": 1})

    assert response.status_code == 400


@pytest.mark.usefixtures("db_session")
async def test_limit_above_max_page_size_is_clamped(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    for i in range(MAX_PAGE_SIZE + 5):
        await _send(client, chat_id, f"message {i}")

    response = await client.get(f"/api/chats/{chat_id}/messages/", params={"limit": MAX_PAGE_SIZE + 50})

    assert response.status_code == 200
    assert len(response.json()["items"]) == MAX_PAGE_SIZE


@pytest.mark.usefixtures("db_session")
async def test_negative_limit_is_rejected(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    await _send(client, chat_id, "one")

    response = await client.get(f"/api/chats/{chat_id}/messages/", params={"limit": -1})

    assert response.status_code == 400
