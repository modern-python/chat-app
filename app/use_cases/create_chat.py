import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.database import tables
from app.exceptions import ValidationError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.schemas.api import CreateChatRequest


_DIRECT_CHAT_MEMBER_COUNT: typing.Final = 2


def _direct_key(member_ids: set[int]) -> str:
    if len(member_ids) != _DIRECT_CHAT_MEMBER_COUNT:
        msg = "A direct chat must have exactly two distinct members"
        raise ValidationError(msg)
    low, high = sorted(member_ids)
    return tables.build_direct_key(low, high)


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class CreateChatUseCase:
    transaction: Transaction
    chats_repository: ChatsRepository
    chat_members_repository: ChatMembersRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor, data: CreateChatRequest) -> tuple[tables.ChatsTable, bool]:
        member_ids: typing.Final = {actor.id, *data.member_ids}
        async with self.transaction:
            if data.chat_type is tables.ChatType.DIRECT:
                chat, created = await self.chats_repository.get_or_create_direct(
                    direct_key=_direct_key(member_ids), created_by_id=actor.id
                )
            else:
                chat = await self.chats_repository.create(
                    tables.ChatsTable(chat_type=data.chat_type, title=data.title, created_by_id=actor.id),
                    auto_refresh=False,
                )
                created = True
            if created:
                await self.chat_members_repository.add_members(chat, sorted(member_ids))
            else:
                chat = await self.chats_repository.fetch_with_members(chat.id)
            await self.transaction.commit()
        return chat, created
