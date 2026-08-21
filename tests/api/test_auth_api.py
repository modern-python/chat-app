import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import jwt_cookie_auth
from app.database import tables


REGISTRATION = {"username": "alice", "password": "hunter2hunter2", "display_name": "Alice"}


@pytest.mark.usefixtures("db_session")
async def test_register_returns_user_and_sets_cookie(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register/", json=REGISTRATION)
    assert response.status_code == 201
    assert response.json()["username"] == "alice"
    assert "password" not in response.text
    assert "token" in response.cookies


@pytest.mark.usefixtures("db_session")
async def test_register_rejects_duplicate_username(client: AsyncClient) -> None:
    await client.post("/api/auth/register/", json=REGISTRATION)
    response = await client.post("/api/auth/register/", json=REGISTRATION)
    assert response.status_code == 409


@pytest.mark.usefixtures("db_session")
async def test_login_succeeds_with_correct_password(client: AsyncClient) -> None:
    await client.post("/api/auth/register/", json=REGISTRATION)
    response = await client.post(
        "/api/auth/login/",
        json={"username": "alice", "password": "hunter2hunter2"},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alice"


@pytest.mark.usefixtures("db_session")
async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    await client.post("/api/auth/register/", json=REGISTRATION)
    response = await client.post(
        "/api/auth/login/",
        json={"username": "alice", "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.usefixtures("db_session")
async def test_login_rejects_unknown_username(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login/",
        json={"username": "nobody", "password": "hunter2hunter2"},
    )
    assert response.status_code == 401


@pytest.mark.usefixtures("db_session")
async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me/")
    assert response.status_code == 401


@pytest.mark.usefixtures("db_session")
async def test_me_returns_the_logged_in_user(client: AsyncClient) -> None:
    await client.post("/api/auth/register/", json=REGISTRATION)
    response = await client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json()["username"] == "alice"


@pytest.mark.usefixtures("db_session")
async def test_logout_clears_the_cookie(client: AsyncClient) -> None:
    await client.post("/api/auth/register/", json=REGISTRATION)
    logout_response = await client.post("/api/auth/logout/")
    assert logout_response.status_code == 204
    me_response = await client.get("/api/auth/me/")
    assert me_response.status_code == 401


async def test_password_is_stored_hashed(client: AsyncClient, db_session: AsyncSession) -> None:
    await client.post("/api/auth/register/", json=REGISTRATION)
    stored = await db_session.scalar(sa.select(tables.UsersTable.password_hash))
    assert stored is not None
    assert stored.startswith("$argon2")


async def test_me_rejects_tampered_cookie(client: AsyncClient) -> None:
    client.cookies.set(jwt_cookie_auth.key, "tampered.not-a-jwt.value")
    response = await client.get("/api/auth/me/")
    assert response.status_code == 401


@pytest.mark.usefixtures("db_session")
async def test_me_rejects_token_with_non_numeric_subject(client: AsyncClient) -> None:
    # Exercises retrieve_user_handler's int(token.sub) ValueError guard: Token only requires
    # sub to be a non-empty string, so a forged/malformed subject must 401, not 500.
    token = jwt_cookie_auth.create_token(identifier="not-a-number")
    client.cookies.set(jwt_cookie_auth.key, token)
    response = await client.get("/api/auth/me/")
    assert response.status_code == 401


@pytest.mark.usefixtures("db_session")
async def test_me_rejects_token_for_a_user_that_no_longer_exists(client: AsyncClient) -> None:
    # A validly signed token whose subject has no matching row: session.get returns None and
    # the middleware must turn that into 401, not treat it as an authenticated request.
    token = jwt_cookie_auth.create_token(identifier="999999999")
    client.cookies.set(jwt_cookie_auth.key, token)
    response = await client.get("/api/auth/me/")
    assert response.status_code == 401
