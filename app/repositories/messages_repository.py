import typing
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from advanced_alchemy.filters import LimitOffset
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from app.database import tables


class MessagesRepository(SQLAlchemyAsyncRepositoryService[tables.MessagesTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.MessagesTable]):
        model_type = tables.MessagesTable

    repository_type = BaseRepository

    async def fetch_by_idempotency_key(self, idempotency_key: uuid.UUID) -> tables.MessagesTable | None:
        return await self.get_one_or_none(idempotency_key=idempotency_key)

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
