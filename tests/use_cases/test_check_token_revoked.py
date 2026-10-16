import asyncio
import typing

import asyncpg
import modern_di

from app import ioc
from app.database.resources import create_database_engine


async def test_revocation_check_sends_no_transaction_statements(di_container: modern_di.Container) -> None:
    engine: typing.Final = create_database_engine()
    di_container.override(ioc.Database.database_engine, engine)
    queries: typing.Final[list[asyncpg.connection.LoggedQuery]] = []

    try:
        async with engine.connect() as connection:
            driver_connection = (await connection.get_raw_connection()).driver_connection
            assert isinstance(driver_connection, asyncpg.Connection)
        driver_connection.add_query_logger(queries.append)

        async with di_container.build_child_container(scope=modern_di.Scope.REQUEST) as container:
            check_token_revoked = container.resolve_provider(ioc.UseCases.check_token_revoked_use_case)
            assert await check_token_revoked(jti="unknown") is False
        await asyncio.sleep(0)
    finally:
        di_container.reset_override(ioc.Database.database_engine)
        await engine.dispose()

    assert not {"BEGIN;", "COMMIT;", "ROLLBACK;"} & {logged.query for logged in queries}, queries
