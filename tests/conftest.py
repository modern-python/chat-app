import typing

import litestar
import modern_di
import modern_di_litestar
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import ioc
from app.api.app import build_app
from app.database.resources import create_database_engine, create_session


@pytest.fixture
async def app() -> typing.AsyncIterator[litestar.Litestar]:
    app_ = build_app()
    async with LifespanManager(app_):  # ty: ignore[invalid-argument-type]
        yield app_


@pytest.fixture
async def client(app: litestar.Litestar) -> typing.AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),  # ty: ignore[invalid-argument-type]
        base_url="http://test",
    ) as client_:
        yield client_


@pytest.fixture
async def di_container(app: litestar.Litestar) -> typing.AsyncIterator[modern_di.Container]:
    container = modern_di_litestar.fetch_di_container(app)
    try:
        yield container
    finally:
        await container.close_async()


@pytest.fixture
async def db_session(di_container: modern_di.Container) -> typing.AsyncIterator[AsyncSession]:
    engine = create_database_engine()
    connection = await engine.connect()
    transaction = await connection.begin()
    di_container.override(ioc.Database.database_engine, connection)

    try:
        yield create_session(connection)
    finally:
        if connection.in_transaction():
            await transaction.rollback()
        await connection.close()
        await engine.dispose()
        di_container.reset_override(ioc.Database.database_engine)
