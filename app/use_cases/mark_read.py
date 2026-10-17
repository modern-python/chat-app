import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.database import tables
from app.exceptions import PermissionDeniedError, ValidationError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.schemas.api import MarkReadRequest


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class MarkReadUseCase:
    transaction: Transaction
    chat_members_repository: ChatMembersRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor, chat_id: int, data: MarkReadRequest) -> tables.ChatMembersTable:
        async with self.transaction:
            found: typing.Final = await self.chat_members_repository.fetch_member_and_message_exists(
                chat_id, actor.id, data.last_read_message_id
            )
            if found is None:
                msg = "Not a member of this chat"
                raise PermissionDeniedError(msg)

            member, message_exists = found
            if not message_exists:
                msg = "last_read_message_id does not name a message in this chat"
                raise ValidationError(msg)

            updated = await self.chat_members_repository.mark_read(member.id, data.last_read_message_id)
            await self.transaction.commit()
            # Safe inside the block: commit() ended the transaction, so __aexit__ only closes.
            return updated
