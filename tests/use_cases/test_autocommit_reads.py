import contextlib
import typing

import modern_di
import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import ioc
from app.actor import Actor
from app.database.resources import create_database_engine
from app.exceptions import PermissionDeniedError


UNKNOWN_ACTOR: typing.Final = Actor(id=-1)


@pytest.mark.parametrize(
    ("provider", "kwargs"),
    [
        (ioc.UseCases.check_token_revoked_use_case, {"jti": "unknown"}),
        (ioc.UseCases.authenticate_user_use_case, {"username": "nobody", "password": "hunter2hunter2"}),
        (ioc.UseCases.fetch_user_use_case, {"actor": UNKNOWN_ACTOR}),
        (ioc.UseCases.fetch_chats_use_case, {"actor": UNKNOWN_ACTOR}),
        (ioc.UseCases.fetch_chat_use_case, {"actor": UNKNOWN_ACTOR, "chat_id": -1}),
    ],
)
async def test_single_statement_read_sends_no_begin_or_commit(
    di_container: modern_di.Container,
    provider: modern_di.providers.Factory[typing.Any],
    kwargs: dict[str, typing.Any],
) -> None:
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
            use_case: typing.Final = container.resolve_provider(provider)
            with contextlib.suppress(PermissionDeniedError):
                await use_case(**kwargs)
    finally:
        di_container.reset_override(ioc.Database.database_engine)
        await engine.dispose()

    assert in_transaction == [False]
