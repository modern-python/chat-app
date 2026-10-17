import typing
from collections.abc import Iterable, Sequence

import sqlalchemy as sa
from advanced_alchemy.exceptions import wrap_sqlalchemy_exception
from advanced_alchemy.repository import DEFAULT_ERROR_MESSAGE_TEMPLATES, SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from app.database import tables


class ChatMembersRepository(SQLAlchemyAsyncRepositoryService[tables.ChatMembersTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.ChatMembersTable]):
        model_type = tables.ChatMembersTable

    repository_type = BaseRepository

    async def is_member(self, chat_id: int, user_id: int) -> bool:
        return await self.exists(chat_id=chat_id, user_id=user_id)

    async def add_members(self, chat_id: int, user_ids: Iterable[int]) -> Sequence[tables.ChatMembersTable]:
        with wrap_sqlalchemy_exception(error_messages=DEFAULT_ERROR_MESSAGE_TEMPLATES, dialect_name="postgresql"):
            result: typing.Final = await self.repository.session.scalars(
                sa.insert(tables.ChatMembersTable).returning(tables.ChatMembersTable),
                [{"chat_id": chat_id, "user_id": user_id} for user_id in sorted(user_ids)],
            )
        return result.all()

    async def list_for_chat(self, chat_id: int) -> Sequence[tables.ChatMembersTable]:
        return await self.get_many(
            tables.ChatMembersTable.chat_id == chat_id, order_by=tables.ChatMembersTable.user_id.asc()
        )

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
