import dataclasses

from db_retry import postgres_retry

from app.actor import Actor
from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchChatUseCase:
    chats_repository: ChatsRepository
    chat_members_repository: ChatMembersRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor, chat_id: int) -> tables.ChatsTable:
        if not await self.chat_members_repository.is_member(chat_id, actor.id):
            msg = "Not a member of this chat"
            raise PermissionDeniedError(msg)
        return await self.chats_repository.fetch_with_members(chat_id)
