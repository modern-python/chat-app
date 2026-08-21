import typing
from collections.abc import Sequence

import sqlalchemy as sa
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import orm

from app.database import tables


class ChatsRepository(SQLAlchemyAsyncRepositoryService[tables.ChatsTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.ChatsTable]):
        model_type = tables.ChatsTable

    repository_type = BaseRepository

    async def fetch_with_members(self, chat_id: int) -> tables.ChatsTable:
        return await self.get_one(
            tables.ChatsTable.id == chat_id,
            load=[orm.selectinload(tables.ChatsTable.members)],
        )

    async def fetch_direct_by_key(self, direct_key: str) -> tables.ChatsTable | None:
        return await self.get_one_or_none(
            tables.ChatsTable.direct_key == direct_key,
            load=[orm.selectinload(tables.ChatsTable.members)],
        )

    async def list_for_user(self, user_id: int) -> Sequence[sa.Row[tuple[tables.ChatsTable, int]]]:
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
            sa.select(tables.ChatsTable, unread_count)
            .join(tables.ChatMembersTable, tables.ChatMembersTable.chat_id == tables.ChatsTable.id)
            .where(tables.ChatMembersTable.user_id == user_id)
            .order_by(sa.func.coalesce(tables.ChatsTable.last_message_id, 0).desc())
        )
        result: typing.Final = await self.repository.session.execute(statement)
        return result.all()
