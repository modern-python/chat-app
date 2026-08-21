import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app.database import tables
from app.exceptions import PermissionDeniedError
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
    async def __call__(self, actor: tables.UsersTable, data: CreateChatRequest) -> tables.ChatsTable:
        member_ids: typing.Final = {actor.id, *data.member_ids}
        direct_key: str | None = None

        if data.chat_type is tables.ChatType.DIRECT:
            if len(member_ids) != _DIRECT_CHAT_MEMBER_COUNT:
                msg = "A direct chat must have exactly two distinct members"
                raise PermissionDeniedError(msg)
            direct_key = tables.build_direct_key(*sorted(member_ids))

            # Read-only lookup kept outside the transaction: Transaction.__aexit__ rolls back
            # whenever no commit happened, and AsyncSession.rollback() expires every loaded
            # attribute (independent of expire_on_commit), which would detach `existing` from
            # its session and break attribute access (e.g. `.members`) after this returns.
            existing = await self.chats_repository.fetch_direct_by_key(direct_key)
            if existing is not None:
                return existing

        async with self.transaction:
            chat = await self.chats_repository.create(
                tables.ChatsTable(
                    chat_type=data.chat_type,
                    title=data.title if data.chat_type is tables.ChatType.GROUP else None,
                    created_by_id=actor.id,
                    direct_key=direct_key,
                )
            )
            for user_id in sorted(member_ids):
                await self.chat_members_repository.create(tables.ChatMembersTable(chat_id=chat.id, user_id=user_id))
            await self.transaction.commit()

        # Kept outside the transaction for the same reason as the lookup above: querying
        # inside `async with self.transaction` after commit() would autobegin a fresh,
        # uncommitted read that __aexit__ then rolls back and closes the session on,
        # detaching the freshly loaded `members` relationship before the caller sees it.
        return await self.chats_repository.fetch_with_members(chat.id)
