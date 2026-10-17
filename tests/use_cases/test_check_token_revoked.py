import typing

import modern_di
import sqlalchemy as sa
from sqlalchemy import event

from app import ioc
from app.database.resources import create_database_engine


async def test_revocation_check_sends_no_begin_or_commit(di_container: modern_di.Container) -> None:
    engine: typing.Final = create_database_engine()
    in_transaction: typing.Final[list[bool]] = []

    def record(connection: sa.Connection, *_: object) -> None:
        driver_connection = connection.connection.driver_connection
        assert driver_connection is not None
        in_transaction.append(driver_connection.is_in_transaction())

    event.listen(engine.sync_engine, "after_cursor_execute", record)
    di_container.override(ioc.Database.database_engine, engine)
    try:
        async with di_container.build_child_container(scope=modern_di.Scope.REQUEST) as container:
            use_case: typing.Final = container.resolve_provider(ioc.UseCases.check_token_revoked_use_case)
            assert await use_case(jti="unknown") is False
    finally:
        di_container.reset_override(ioc.Database.database_engine)
        await engine.dispose()

    assert in_transaction == [False]
