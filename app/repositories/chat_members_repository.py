import typing

import sqlalchemy as sa
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from app.database import tables


class ChatMembersRepository(SQLAlchemyAsyncRepositoryService[tables.ChatMembersTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.ChatMembersTable]):
        model_type = tables.ChatMembersTable

    repository_type = BaseRepository

    async def is_member(self, chat_id: int, user_id: int) -> bool:
        return await self.exists(chat_id=chat_id, user_id=user_id)

    async def fetch_member(self, chat_id: int, user_id: int) -> tables.ChatMembersTable | None:
        return await self.get_one_or_none(chat_id=chat_id, user_id=user_id)

    async def mark_read(self, member_id: int, requested_message_id: int) -> tables.ChatMembersTable:
        """Advance last_read_message_id to GREATEST(current, requested), atomically.

        The GREATEST() is computed by the UPDATE itself rather than in Python from a prior read:
        a read-modify-write across two calls (fetch_member, then update) would let two concurrent
        POST /read/ requests interleave and let the lower id win. This UPDATE's row lock
        serializes concurrent writers, and each one recomputes GREATEST against whatever the
        winner of that lock just committed.
        """
        statement: typing.Final = (
            sa.update(tables.ChatMembersTable)
            .where(tables.ChatMembersTable.id == member_id)
            .values(
                last_read_message_id=sa.func.greatest(
                    sa.func.coalesce(tables.ChatMembersTable.last_read_message_id, 0), requested_message_id
                )
            )
            .returning(tables.ChatMembersTable)
        )
        result: typing.Final = await self.repository.session.execute(statement)
        return result.scalar_one()
