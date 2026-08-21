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
    async def __call__(
        self, *, actor: tables.UsersTable, chat_id: int, data: MarkReadRequest
    ) -> tables.ChatMembersTable:
        member: typing.Final = await self.chat_members_repository.fetch_member(chat_id, actor.id)
        if member is None:
            msg = "Not a member of this chat"
            raise PermissionDeniedError(msg)

        target_message = await self.messages_repository.get_one_or_none(id=data.last_read_message_id, chat_id=chat_id)
        if target_message is None:
            msg = "last_read_message_id does not name a message in this chat"
            raise ValidationError(msg)

        async with self.transaction:
            updated = await self.chat_members_repository.mark_read(member.id, data.last_read_message_id)
            await self.transaction.commit()
            # Safe inside the block: commit() ended the transaction, so __aexit__ only closes.
            return updated
