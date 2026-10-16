import asyncio
import typing

import advanced_alchemy.exceptions
import asyncpg
import modern_di
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import InterfaceError
from sqlalchemy.ext.asyncio import AsyncSession

from app import ioc
from app.actor import Actor
from app.database.resources import create_database_engine
from app.exceptions import PermissionDeniedError


pytestmark = pytest.mark.xfail(
    raises=(advanced_alchemy.exceptions.IntegrityError, InterfaceError),
    reason="the released db-retry does not retry a closed connection; modern-python/db-retry#69 does",
    strict=True,
)

UNKNOWN_ACTOR: typing.Final = Actor(id=-1)


@pytest.fixture
async def request_container(di_container: modern_di.Container) -> typing.AsyncIterator[modern_di.Container]:
    engine: typing.Final = create_database_engine()
    di_container.override(ioc.Database.database_engine, engine)
    try:
        async with di_container.build_child_container(scope=modern_di.Scope.REQUEST) as container:
            yield container
    finally:
        di_container.reset_override(ioc.Database.database_engine)
        await engine.dispose()


@pytest.fixture
async def lost_connection(request_container: modern_di.Container) -> None:
    """Leave the request session holding a pooled connection whose backend was terminated."""
    session: typing.Final = request_container.resolve_provider(ioc.Database.database_session)
    assert isinstance(session, AsyncSession)
    connection: typing.Final = await session.connection()
    pid: typing.Final = await connection.scalar(sa.text("SELECT pg_backend_pid()"))
    driver_connection: typing.Final = (await connection.get_raw_connection()).driver_connection
    assert driver_connection is not None
    closed: typing.Final = asyncio.Event()
    driver_connection.add_termination_listener(lambda _: closed.set())
    killer: typing.Final = await asyncpg.connect(
        connection.engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    try:
        await killer.execute("SELECT pg_terminate_backend($1)", pid)
    finally:
        await killer.close()
    await asyncio.wait_for(closed.wait(), timeout=5)


@pytest.mark.usefixtures("lost_connection")
@pytest.mark.parametrize(
    ("provider", "kwargs", "expected"),
    [
        (ioc.UseCases.authenticate_user_use_case, {"username": "nobody", "password": "hunter2hunter2"}, None),
        (ioc.UseCases.check_token_revoked_use_case, {"jti": "unknown"}, False),
        (ioc.UseCases.fetch_chats_use_case, {"actor": UNKNOWN_ACTOR}, []),
        (ioc.UseCases.fetch_user_use_case, {"actor": UNKNOWN_ACTOR}, None),
    ],
)
async def test_read_use_case_recovers_from_a_lost_connection(
    request_container: modern_di.Container,
    provider: modern_di.providers.Factory[typing.Any],
    kwargs: dict[str, typing.Any],
    expected: object,
) -> None:
    use_case: typing.Final = request_container.resolve_provider(provider)
    assert await use_case(**kwargs) == expected


@pytest.mark.usefixtures("lost_connection")
@pytest.mark.parametrize("provider", [ioc.UseCases.fetch_chat_use_case, ioc.UseCases.fetch_messages_use_case])
async def test_membership_gated_use_case_recovers_from_a_lost_connection(
    request_container: modern_di.Container, provider: modern_di.providers.Factory[typing.Any]
) -> None:
    use_case: typing.Final = request_container.resolve_provider(provider)
    with pytest.raises(PermissionDeniedError):
        await use_case(actor=UNKNOWN_ACTOR, chat_id=-1)
