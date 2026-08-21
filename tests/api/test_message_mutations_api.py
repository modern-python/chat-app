import pytest
from httpx import AsyncClient

from tests.api.helpers import create_direct_chat as _create_direct_chat
from tests.api.helpers import login as _login
from tests.api.helpers import register as _register
from tests.api.helpers import send as _send


@pytest.mark.usefixtures("db_session")
async def test_author_can_edit_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")

    response = await client.patch(f"/api/messages/{message['id']}/", json={"text": "fixed"})

    assert response.status_code == 200
    assert response.json()["text"] == "fixed"
    assert response.json()["edited_at"] is not None


@pytest.mark.usefixtures("db_session")
async def test_non_author_member_cannot_edit_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")
    await _login(client, "bob")  # bob is a member of the chat but not the author

    response = await client.patch(f"/api/messages/{message['id']}/", json={"text": "nope"})

    assert response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_non_member_cannot_edit_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")
    await _register(client, "mallory")  # mallory is not in the chat at all

    response = await client.patch(f"/api/messages/{message['id']}/", json={"text": "nope"})

    assert response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_author_can_delete_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")

    response = await client.delete(f"/api/messages/{message['id']}/")

    assert response.status_code == 204


@pytest.mark.usefixtures("db_session")
async def test_non_author_member_cannot_delete_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")
    await _login(client, "bob")  # bob is a member of the chat but not the author

    response = await client.delete(f"/api/messages/{message['id']}/")

    assert response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_non_member_cannot_delete_message(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")
    await _register(client, "mallory")  # mallory is not in the chat at all

    response = await client.delete(f"/api/messages/{message['id']}/")

    assert response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_editing_a_missing_message_returns_404(client: AsyncClient) -> None:
    await _register(client, "alice")

    response = await client.patch("/api/messages/999999/", json={"text": "nope"})

    assert response.status_code == 404


@pytest.mark.usefixtures("db_session")
async def test_deleting_a_missing_message_returns_404(client: AsyncClient) -> None:
    await _register(client, "alice")

    response = await client.delete("/api/messages/999999/")

    assert response.status_code == 404


async def test_edit_message_requires_authentication(client: AsyncClient) -> None:
    response = await client.patch("/api/messages/1/", json={"text": "nope"})
    assert response.status_code == 401


async def test_delete_message_requires_authentication(client: AsyncClient) -> None:
    response = await client.delete("/api/messages/1/")
    assert response.status_code == 401


@pytest.mark.usefixtures("db_session")
async def test_editing_a_deleted_message_returns_409(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")
    await client.delete(f"/api/messages/{message['id']}/")

    response = await client.patch(f"/api/messages/{message['id']}/", json={"text": "nope"})

    assert response.status_code == 409


@pytest.mark.usefixtures("db_session")
async def test_deleting_an_already_deleted_message_returns_204(client: AsyncClient) -> None:
    chat_id, _ = await _create_direct_chat(client)
    message = await _send(client, chat_id, "hi")
    first = await client.delete(f"/api/messages/{message['id']}/")

    second = await client.delete(f"/api/messages/{message['id']}/")

    assert first.status_code == 204
    assert second.status_code == 204
