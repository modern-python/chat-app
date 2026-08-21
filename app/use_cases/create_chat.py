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
    async def __call__(self, actor: tables.UsersTable, data: CreateChatRequest) -> tuple[tables.ChatsTable, bool]:
        member_ids: typing.Final = {actor.id, *data.member_ids}
        direct_key: str | None = None

        if data.chat_type is tables.ChatType.DIRECT:
            if len(member_ids) != _DIRECT_CHAT_MEMBER_COUNT:
                msg = "A direct chat must have exactly two distinct members"
                raise ValidationError(msg)
            low, high = sorted(member_ids)
            direct_key = tables.build_direct_key(low, high)

            # Kept outside the `async with` block below: Transaction.__aexit__ unconditionally
            # rolls back and closes the session whenever it is left with an open, uncommitted
            # transaction (session.in_transaction() True with no prior commit()), which expires
            # and detaches every loaded attribute. A `return` from inside the block after this
            # read - with no commit following it - would trigger exactly that on `existing`.
            # (For direct chats specifically, this SELECT autobegins the session's transaction,
            # so the `async with self.transaction:` block below actually *joins* that same
            # transaction rather than starting a new one - see Transaction.__aenter__. That does
            # not change the __aexit__ hazard above; it only means direct and group chats reach
            # the block by different routes.)
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
                # Two concurrent requests to open the same direct chat both passed the
                # fetch_direct_by_key pre-check above and both tried to insert; the loser hits
                # uq_chats_direct_key here. Group chats have no unique constraint on `chats` to
                # violate, so an unexpected DuplicateKeyError there re-raises and maps to the
                # standard 409 instead of being funnelled into this direct-chat recovery path.
                if direct_key is None:
                    raise
                # Roll back and re-read the winner's row outside this block (same __aexit__
                # hazard as the comment above): a `return` from in here without a commit
                # first would detach whatever `fetch_direct_by_key` loaded, same as before.
                await self.transaction.rollback()
            else:
                for user_id in sorted(member_ids):
                    await self.chat_members_repository.create(tables.ChatMembersTable(chat_id=chat.id, user_id=user_id))
                await self.transaction.commit()

        if chat is None:
            existing = await self.chats_repository.fetch_direct_by_key(direct_key)  # ty: ignore[invalid-argument-type]
            if existing is None:  # pragma: no cover - defensive: the unique constraint guarantees a match here
                msg = "Direct chat creation raced but the resulting row could not be found"
                raise RuntimeError(msg)
            return existing, False

        # Kept outside the `async with` block for the same reason as the lookup above.
        return await self.chats_repository.fetch_with_members(chat.id), True
