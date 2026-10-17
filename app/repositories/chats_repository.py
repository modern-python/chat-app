import datetime as dt
import typing
from collections.abc import Sequence

import sqlalchemy as sa
from advanced_alchemy.exceptions import wrap_sqlalchemy_exception
from advanced_alchemy.repository import DEFAULT_ERROR_MESSAGE_TEMPLATES, SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import orm
from sqlalchemy.dialects import postgresql

from app.database import tables


_WITH_MEMBERS: typing.Final[dict[str, typing.Any]] = {
    "load": [orm.joinedload(tables.ChatsTable.members)],
    "uniquify": True,
    # A chat already in the identity map keeps its noload members without this.
    "execution_options": {"populate_existing": True},
}


class ChatsRepository(SQLAlchemyAsyncRepositoryService[tables.ChatsTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.ChatsTable]):
        model_type = tables.ChatsTable

    repository_type = BaseRepository

    async def fetch_with_members(self, chat_id: int) -> tables.ChatsTable:
        return await self.get_one(tables.ChatsTable.id == chat_id, **_WITH_MEMBERS)

    async def find_with_members(self, chat_id: int) -> tables.ChatsTable | None:
        return await self.get_one_or_none(tables.ChatsTable.id == chat_id, **_WITH_MEMBERS)

    async def set_last_message(self, chat_id: int, message_id: int) -> None:
        await self.repository.session.execute(
            sa.update(tables.ChatsTable)
            .where(tables.ChatsTable.id == chat_id)
            .values(last_message_id=message_id, updated_at=dt.datetime.now(tz=dt.UTC))
        )

    async def repoint_last_message(self, chat_id: int, deleted_message_id: int) -> None:
        newest_active: typing.Final = (
            sa.select(tables.MessagesTable.id)
            .where(tables.MessagesTable.chat_id == chat_id, tables.MessagesTable.deleted_at.is_(None))
            .order_by(tables.MessagesTable.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        await self.repository.session.execute(
            sa.update(tables.ChatsTable)
            .where(tables.ChatsTable.id == chat_id, tables.ChatsTable.last_message_id == deleted_message_id)
            .values(last_message_id=newest_active, updated_at=dt.datetime.now(tz=dt.UTC))
        )

    async def get_or_create_direct(self, *, direct_key: str, created_by_id: int) -> tuple[tables.ChatsTable, bool]:
        statement = postgresql.insert(tables.ChatsTable).values(
            chat_type=tables.ChatType.DIRECT, created_by_id=created_by_id, direct_key=direct_key
        )
        statement = statement.on_conflict_do_update(
            index_elements=[tables.ChatsTable.direct_key],
            set_={"direct_key": statement.excluded.direct_key},
        )
        # xmax is 0 only on a row version this statement inserted.
        created: typing.Final = sa.literal_column("xmax = 0", sa.Boolean)
        with wrap_sqlalchemy_exception(error_messages=DEFAULT_ERROR_MESSAGE_TEMPLATES, dialect_name="postgresql"):
            result: typing.Final = await self.repository.session.execute(
                statement.returning(tables.ChatsTable, created)
            )
        chat, was_created = result.one()
        return chat, was_created

    async def list_for_user(self, user_id: int) -> Sequence[tables.ChatsTable]:
        unread_count: typing.Final = (
            sa.select(sa.func.count(tables.MessagesTable.id))
            .where(
                tables.MessagesTable.chat_id == tables.ChatMembersTable.chat_id,
                tables.MessagesTable.deleted_at.is_(None),
                tables.MessagesTable.user_id.is_distinct_from(tables.ChatMembersTable.user_id),
                tables.MessagesTable.id > sa.func.coalesce(tables.ChatMembersTable.last_read_message_id, 0),
            )
            .correlate(tables.ChatMembersTable)
            .scalar_subquery()
            .label("unread_count")
        )
        statement: typing.Final = (
            sa.select(tables.ChatsTable)
            .options(
                orm.with_expression(tables.ChatsTable.unread_count, unread_count),
                orm.joinedload(tables.ChatsTable.last_message),
            )
            .join(tables.ChatMembersTable, tables.ChatMembersTable.chat_id == tables.ChatsTable.id)
            .where(tables.ChatMembersTable.user_id == user_id)
            .order_by(sa.func.coalesce(tables.ChatsTable.last_message_id, 0).desc())
            # expire_on_commit=False would otherwise leave identity-mapped chats holding stale values.
            .execution_options(populate_existing=True)
        )
        result: typing.Final = await self.repository.session.execute(statement)
        return result.scalars().all()
