import typing

from db_retry import Transaction
from modern_di import Group, Scope, providers

from app.database import resources as database_resources


class Database(Group):
    database_engine = providers.Factory(
        creator=database_resources.create_database_engine,
        cache=providers.CacheSettings(finalizer=database_resources.close_database_engine),
    )
    database_session = providers.Factory(
        scope=Scope.REQUEST,
        creator=database_resources.create_session,
        cache=providers.CacheSettings(finalizer=database_resources.close_session),
    )
    transaction = providers.Factory(
        scope=Scope.REQUEST,
        creator=Transaction,
        kwargs={"session": database_session},
    )


ALL_GROUPS: typing.Final[list[type[Group]]] = [Database]
