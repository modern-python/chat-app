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
