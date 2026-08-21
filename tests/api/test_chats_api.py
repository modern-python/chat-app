import typing

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, username: str) -> int:
    response = await client.post(
        "/api/auth/register/",
        json={"username": username, "password": "hunter2hunter2", "display_name": username.title()},
    )
    user_id: typing.Final = response.json()["id"]
    return user_id


@pytest.mark.usefixtures("db_session")
async def test_create_group_chat_returns_all_members(client: AsyncClient) -> None:
    bob_id = await _register(client, "bob")
    await _register(client, "alice")
    response = await client.post(
        "/api/chats/",
        json={"chat_type": "group", "member_ids": [bob_id], "title": "Team"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Team"
    assert len(response.json()["members"]) == 2


@pytest.mark.usefixtures("db_session")
async def test_get_chat_returns_the_chat_for_a_member(client: AsyncClient) -> None:
    bob_id = await _register(client, "bob")
    await _register(client, "alice")
    chat_id = (await client.post("/api/chats/", json={"chat_type": "direct", "member_ids": [bob_id]})).json()["id"]
    response = await client.get(f"/api/chats/{chat_id}/")
    assert response.status_code == 200
    assert response.json()["id"] == chat_id


@pytest.mark.usefixtures("db_session")
async def test_get_chat_rejects_non_member(client: AsyncClient) -> None:
    bob_id = await _register(client, "bob")
    await _register(client, "alice")
    chat_id = (await client.post("/api/chats/", json={"chat_type": "direct", "member_ids": [bob_id]})).json()["id"]
    await _register(client, "mallory")
    response = await client.get(f"/api/chats/{chat_id}/")
    assert response.status_code == 403


@pytest.mark.usefixtures("db_session")
async def test_create_chat_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/chats/", json={"chat_type": "group", "member_ids": [1]})
    assert response.status_code == 401
