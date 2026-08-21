import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app.database import tables
from app.exceptions import PermissionDeniedError, ValidationError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas.api import MarkReadRequest


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class MarkReadUseCase:
    transaction: Transaction
    chat_members_repository: ChatMembersRepository
    messages_repository: MessagesRepository

    @postgres_retry
    async def __call__(self, actor: tables.UsersTable, chat_id: int, data: MarkReadRequest) -> tables.ChatMembersTable:
        member: typing.Final = await self.chat_members_repository.fetch_member(chat_id, actor.id)
        if member is None:
            msg = "Not a member of this chat"
            raise PermissionDeniedError(msg)

        # The requested marker must name a real message in *this* chat - otherwise a client could
        # set it to an arbitrary large id and permanently zero its own unread count.
        target_message = await self.messages_repository.get_one_or_none(id=data.last_read_message_id, chat_id=chat_id)
        if target_message is None:
            msg = "last_read_message_id does not name a message in this chat"
            raise ValidationError(msg)

        async with self.transaction:
            # Monotonic: an out-of-order or replayed request naming an earlier message must not
            # move the marker backwards and resurrect messages that were already marked read.
            # The GREATEST(...) that enforces this lives in the UPDATE itself (see
            # ChatMembersRepository.mark_read) rather than being computed here from `member`'s
            # already-read value - that would be a read-modify-write race between concurrent
            # POST /read/ calls.
            updated = await self.chat_members_repository.mark_read(member.id, data.last_read_message_id)
            await self.transaction.commit()
            # Returned from inside the block, right after commit(): __aexit__ then sees no open
            # transaction (commit ended it) and only closes the session - it does not roll back,
            # so `updated`'s already-loaded attributes stay usable for the caller. Same strategy
            # as Task 5's EditMessageUseCase.
            return updated
