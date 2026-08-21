import modern_di
import sqlalchemy as sa
from advanced_alchemy.exceptions import NotFoundError
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import QueuePool

from app import ioc
from app.api import exception_handlers
from app.database.resources import close_database_engine, create_database_engine
from app.database.tables import UsersTable
from app.exceptions import PermissionDeniedError
from app.settings import settings
from tests.factories import UserFactory


async def test_health_check_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health/")
    assert response.status_code == 200


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/docs/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "chat-app"


async def test_not_found_error_handler_returns_404() -> None:
    response = exception_handlers.not_found_error_handler(object(), NotFoundError())
    assert response.status_code == 404
    assert response.content == {"detail": "Not found"}


async def test_permission_denied_handler_uses_exception_message() -> None:
    response = exception_handlers.permission_denied_handler(object(), PermissionDeniedError("nope"))
    assert response.status_code == 403
    assert response.content == {"detail": "nope"}


async def test_permission_denied_handler_defaults_message_when_empty() -> None:
    response = exception_handlers.permission_denied_handler(object(), PermissionDeniedError())
    assert response.content == {"detail": "Permission denied"}


async def test_create_database_engine_reads_settings_and_can_be_disposed() -> None:
    engine = create_database_engine()
    try:
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == settings.db_pool_size
        assert engine.url.database == settings.db_dsn_parsed.database
    finally:
        await close_database_engine(engine)


async def test_db_session_insert_is_visible_within_test(db_session: AsyncSession) -> None:
    user = UserFactory.build()
    db_session.add(user)
    await db_session.commit()

    result = await db_session.scalars(sa.select(UsersTable))
    assert len(result.all()) == 1


async def test_db_session_rolls_back_between_tests(db_session: AsyncSession) -> None:
    result = await db_session.scalars(sa.select(UsersTable))
    assert result.all() == []


async def test_di_resolved_session_shares_the_overridden_connection(
    di_container: modern_di.Container,
    db_session: AsyncSession,
) -> None:
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    async with di_container.build_child_container(scope=modern_di.Scope.REQUEST) as request_container:
        resolved_session = request_container.resolve_provider(ioc.Database.database_session)
        result = await resolved_session.scalars(sa.select(UsersTable).where(UsersTable.username == user.username))
        assert result.one().id == user.id
