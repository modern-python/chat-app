import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.chats_repository import ChatsRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchChatUseCase:
    transaction: Transaction
    chats_repository: ChatsRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor, chat_id: int) -> tables.ChatsTable:
        async with self.transaction:
            chat: typing.Final = await self.chats_repository.find_with_members(chat_id)
            await self.transaction.commit()
        if chat is None or all(member.user_id != actor.id for member in chat.members):
            msg = "Not a member of this chat"
            raise PermissionDeniedError(msg)
        return chat
