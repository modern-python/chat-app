import asyncio
import typing

from db_retry import Transaction
from sqlalchemy.ext import asyncio as sa

from app.settings import settings


def create_database_engine() -> sa.AsyncEngine:
    return sa.create_async_engine(
        url=settings.db_dsn_parsed,
        echo=settings.service_debug,
        echo_pool=settings.service_debug,
        pool_size=settings.db_pool_size,
        pool_pre_ping=settings.db_pool_pre_ping,
        max_overflow=settings.db_max_overflow,
    )


async def close_database_engine(engine: sa.AsyncEngine) -> None:
    await engine.dispose()


def create_session(engine: sa.AsyncEngine | sa.AsyncConnection) -> sa.AsyncSession:
    # join_transaction_mode is inert in production; it makes test-bound sessions nest as savepoints.
    return sa.AsyncSession(
        engine,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )


async def close_session(session: sa.AsyncSession) -> None:
    task: typing.Final = asyncio.create_task(session.close())
    await asyncio.shield(task)


def create_autocommit_transaction(session: sa.AsyncSession) -> Transaction:
    # Isolation level can only be set before the session holds a connection; test sessions are bound to one.
    if isinstance(session.bind, sa.AsyncEngine) and not session.in_transaction():
        return Transaction(session=session, isolation_level="AUTOCOMMIT")
    return Transaction(session=session)
