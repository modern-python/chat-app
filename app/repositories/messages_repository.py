import datetime as dt
import typing
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from advanced_alchemy.exceptions import NotFoundError, wrap_sqlalchemy_exception
from advanced_alchemy.filters import LimitOffset
from advanced_alchemy.repository import DEFAULT_ERROR_MESSAGE_TEMPLATES, SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy.dialects import postgresql

from app.database import tables


class MessagesRepository(SQLAlchemyAsyncRepositoryService[tables.MessagesTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.MessagesTable]):
        model_type = tables.MessagesTable

    repository_type = BaseRepository

    async def get_or_create(
        self, *, chat_id: int, user_id: int, idempotency_key: uuid.UUID, text: str
    ) -> tuple[tables.MessagesTable, bool]:
        statement = postgresql.insert(tables.MessagesTable).values(
            chat_id=chat_id, user_id=user_id, idempotency_key=idempotency_key, text=text
        )
        statement = statement.on_conflict_do_update(
            constraint="uk_messages_chat_id_idempotency_key",
            set_={"idempotency_key": statement.excluded.idempotency_key},
        )
        # xmax is 0 only on a row version this statement inserted.
        created: typing.Final = sa.literal_column("xmax = 0", sa.Boolean)
        with wrap_sqlalchemy_exception(error_messages=DEFAULT_ERROR_MESSAGE_TEMPLATES, dialect_name="postgresql"):
            result: typing.Final = await self.repository.session.execute(
                statement.returning(tables.MessagesTable, created)
            )
        message, was_created = result.one()
        return message, was_created

    async def fetch_with_membership(self, message_id: int, user_id: int) -> tuple[tables.MessagesTable, bool]:
        is_member: typing.Final = (
            sa.exists()
            .where(
                tables.ChatMembersTable.chat_id == tables.MessagesTable.chat_id,
                tables.ChatMembersTable.user_id == user_id,
            )
            .label("is_member")
        )
        result: typing.Final = await self.repository.session.execute(
            sa.select(tables.MessagesTable, is_member).where(tables.MessagesTable.id == message_id)
        )
        row: typing.Final = result.one_or_none()
        if row is None:
            msg = "No item found when one was expected"
            raise NotFoundError(msg)
        return row[0], row[1]

    async def edit_text(self, message_id: int, text: str, edited_at: dt.datetime) -> tables.MessagesTable:
        result: typing.Final = await self.repository.session.execute(
            sa.update(tables.MessagesTable)
            .where(tables.MessagesTable.id == message_id)
            .values(text=text, edited_at=edited_at)
            .returning(tables.MessagesTable)
        )
        return result.scalar_one()

    async def soft_delete(self, message_id: int, deleted_at: dt.datetime) -> None:
        await self.repository.session.execute(
            sa.update(tables.MessagesTable).where(tables.MessagesTable.id == message_id).values(deleted_at=deleted_at)
        )

    async def list_page(
        self,
        chat_id: int,
        *,
        before_id: int | None,
        after_id: int | None,
        limit: int,
    ) -> Sequence[tables.MessagesTable]:
        filters: typing.Final[list[sa.ColumnElement[bool]]] = [
            tables.MessagesTable.chat_id == chat_id,
            tables.MessagesTable.deleted_at.is_(None),
        ]
        if after_id is not None:
            filters.append(tables.MessagesTable.id > after_id)
            return await self.get_many(*filters, LimitOffset(limit=limit, offset=0), order_by=[("id", False)])
        if before_id is not None:
            filters.append(tables.MessagesTable.id < before_id)
        return await self.get_many(*filters, LimitOffset(limit=limit, offset=0), order_by=[("id", True)])
