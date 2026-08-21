import dataclasses
import typing

from advanced_alchemy.exceptions import DuplicateKeyError
from db_retry import Transaction, postgres_retry

from app.database import tables
from app.exceptions import ValidationError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.schemas.api import CreateChatRequest


_DIRECT_CHAT_MEMBER_COUNT: typing.Final = 2


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class CreateChatUseCase:
    transaction: Transaction
    chats_repository: ChatsRepository
    chat_members_repository: ChatMembersRepository

    @postgres_retry
    async def __call__(self, *, actor: tables.UsersTable, data: CreateChatRequest) -> tuple[tables.ChatsTable, bool]:
        member_ids: typing.Final = {actor.id, *data.member_ids}
        direct_key: str | None = None

        if data.chat_type is tables.ChatType.DIRECT:
            if len(member_ids) != _DIRECT_CHAT_MEMBER_COUNT:
                msg = "A direct chat must have exactly two distinct members"
                raise ValidationError(msg)
            low, high = sorted(member_ids)
            direct_key = tables.build_direct_key(low, high)

            # Outside the block: __aexit__ rolls back an uncommitted transaction and detaches this.
            existing = await self.chats_repository.fetch_direct_by_key(direct_key)
            if existing is not None:
                return existing, False

        chat: tables.ChatsTable | None = None
        async with self.transaction:
            try:
                chat = await self.chats_repository.create(
                    tables.ChatsTable(
                        chat_type=data.chat_type,
                        title=data.title if data.chat_type is tables.ChatType.GROUP else None,
                        created_by_id=actor.id,
                        direct_key=direct_key,
                    )
                )
            except DuplicateKeyError:
                # Group chats have no unique constraint here, so a collision is not recoverable.
                if direct_key is None:
                    raise
                await self.transaction.rollback()
            else:
                for user_id in sorted(member_ids):
                    await self.chat_members_repository.create(tables.ChatMembersTable(chat_id=chat.id, user_id=user_id))
                await self.transaction.commit()

        if chat is None:
            existing = await self.chats_repository.fetch_direct_by_key(direct_key)  # ty: ignore[invalid-argument-type]
            if existing is None:
                msg = "Direct chat creation raced but the resulting row could not be found"
                raise RuntimeError(msg)
            return existing, False

        return await self.chats_repository.fetch_with_members(chat.id), True
