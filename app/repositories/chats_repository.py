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
