import asyncio
import typing
import uuid

import asyncpg
import modern_di
import pytest
import sqlalchemy as sa
from advanced_alchemy.exceptions import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app import ioc
from app.actor import Actor
from app.database import tables
from app.database.resources import create_database_engine
from app.exceptions import PermissionDeniedError
from app.schemas.api import CreateChatRequest, MarkReadRequest, SendMessageRequest
from app.settings import settings


UNKNOWN_ACTOR: typing.Final = Actor(id=-1)


@pytest.fixture
async def request_container(di_container: modern_di.Container) -> typing.AsyncIterator[modern_di.Container]:
    engine: typing.Final = create_database_engine(settings)
    di_container.override(ioc.Database.database_engine, engine)
    try:
        async with di_container.build_child_container(scope=modern_di.Scope.REQUEST) as container:
            yield container
    finally:
        di_container.reset_override(ioc.Database.database_engine)
        await engine.dispose()


async def _watch_backend(connection: AsyncConnection) -> tuple[int, asyncio.Event]:
    pid: typing.Final = await connection.scalar(sa.text("SELECT pg_backend_pid()"))
    driver_connection: typing.Final = (await connection.get_raw_connection()).driver_connection
    assert driver_connection is not None
    closed: typing.Final = asyncio.Event()
    driver_connection.add_termination_listener(lambda _: closed.set())
    return pid, closed


async def _terminate_backend(engine: AsyncEngine, pid: int, closed: asyncio.Event) -> None:
    killer: typing.Final = await asyncpg.connect(
        engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    )
    try:
        await killer.execute("SELECT pg_terminate_backend($1)", pid)
    finally:
        await killer.close()
    await asyncio.wait_for(closed.wait(), timeout=5)


@pytest.fixture
async def lost_connection(request_container: modern_di.Container) -> None:
    """Leave the request session holding a pooled connection whose backend was terminated."""
    session: typing.Final = request_container.resolve_provider(ioc.Database.database_session)
    assert isinstance(session, AsyncSession)
    connection: typing.Final = await session.connection()
    await _terminate_backend(connection.engine, *await _watch_backend(connection))


@pytest.fixture
async def lost_pooled_connection(request_container: modern_di.Container) -> None:
    """Leave the engine's pool holding one idle connection whose backend was terminated."""
    engine: typing.Final = request_container.resolve_provider(ioc.Database.database_engine)
    assert isinstance(engine, AsyncEngine)
    async with engine.connect() as connection:
        watched: typing.Final = await _watch_backend(connection)
    await _terminate_backend(engine, *watched)


AUTOCOMMIT_READ_USE_CASES: typing.Final = pytest.mark.parametrize(
    ("provider", "kwargs", "expected"),
    [
        (ioc.UseCases.authenticate_user_use_case, {"username": "nobody", "password": "hunter2hunter2"}, None),
        (ioc.UseCases.fetch_chats_use_case, {"actor": UNKNOWN_ACTOR}, []),
        (ioc.UseCases.fetch_user_use_case, {"actor": UNKNOWN_ACTOR}, None),
        (ioc.UseCases.check_token_revoked_use_case, {"jti": "unknown"}, False),
    ],
)


@pytest.mark.usefixtures("lost_pooled_connection")
@AUTOCOMMIT_READ_USE_CASES
async def test_read_use_case_recovers_from_a_connection_lost_while_pooled(
    request_container: modern_di.Container,
    provider: modern_di.providers.Factory[typing.Any],
    kwargs: dict[str, typing.Any],
    expected: object,
) -> None:
    use_case: typing.Final = request_container.resolve_provider(provider)
    assert await use_case(**kwargs) == expected


_TRANSACTIONAL_MEMBERSHIP_GATED_CASES: typing.Final = [
    (ioc.UseCases.fetch_messages_use_case, {}),
    (
        ioc.UseCases.create_message_use_case,
        {"data": SendMessageRequest(idempotency_key=uuid.uuid4(), text="hello")},
    ),
    (ioc.UseCases.mark_read_use_case, {"data": MarkReadRequest(last_read_message_id=1)}),
]
TRANSACTIONAL_MEMBERSHIP_GATED_USE_CASES: typing.Final = pytest.mark.parametrize(
    ("provider", "kwargs"), _TRANSACTIONAL_MEMBERSHIP_GATED_CASES
)
MEMBERSHIP_GATED_USE_CASES: typing.Final = pytest.mark.parametrize(
    ("provider", "kwargs"), [(ioc.UseCases.fetch_chat_use_case, {}), *_TRANSACTIONAL_MEMBERSHIP_GATED_CASES]
)


@pytest.mark.usefixtures("lost_connection")
@TRANSACTIONAL_MEMBERSHIP_GATED_USE_CASES
async def test_membership_gated_use_case_recovers_from_a_lost_connection(
    request_container: modern_di.Container,
    provider: modern_di.providers.Factory[typing.Any],
    kwargs: dict[str, typing.Any],
) -> None:
    use_case: typing.Final = request_container.resolve_provider(provider)
    with pytest.raises(PermissionDeniedError):
        await use_case(actor=UNKNOWN_ACTOR, chat_id=-1, **kwargs)


@pytest.mark.usefixtures("lost_pooled_connection")
@MEMBERSHIP_GATED_USE_CASES
async def test_membership_gated_use_case_recovers_from_a_connection_lost_while_pooled(
    request_container: modern_di.Container,
    provider: modern_di.providers.Factory[typing.Any],
    kwargs: dict[str, typing.Any],
) -> None:
    use_case: typing.Final = request_container.resolve_provider(provider)
    with pytest.raises(PermissionDeniedError):
        await use_case(actor=UNKNOWN_ACTOR, chat_id=-1, **kwargs)


@pytest.mark.usefixtures("lost_pooled_connection")
async def test_direct_chat_upsert_recovers_from_a_connection_lost_while_pooled(
    request_container: modern_di.Container,
) -> None:
    use_case: typing.Final = request_container.resolve_provider(ioc.UseCases.create_chat_use_case)
    with pytest.raises(IntegrityError):
        await use_case(actor=UNKNOWN_ACTOR, data=CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[1]))
