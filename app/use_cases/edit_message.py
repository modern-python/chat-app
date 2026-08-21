import dataclasses
import datetime

from db_retry import Transaction, postgres_retry

from app.database import tables
from app.exceptions import ConflictError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas.api import EditMessageRequest
from app.use_cases.message_authorization import fetch_message_for_author


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class EditMessageUseCase:
    transaction: Transaction
    messages_repository: MessagesRepository
    chat_members_repository: ChatMembersRepository

    @postgres_retry
    async def __call__(
        self, actor: tables.UsersTable, message_id: int, data: EditMessageRequest
    ) -> tables.MessagesTable:
        async with self.transaction:
            message = await fetch_message_for_author(
                messages_repository=self.messages_repository,
                chat_members_repository=self.chat_members_repository,
                actor=actor,
                message_id=message_id,
                action="edit",
            )
            if message.deleted_at is not None:
                msg = "This message has been deleted"
                raise ConflictError(msg)
            message.text = data.text
            message.edited_at = datetime.datetime.now(tz=datetime.UTC)
            updated = await self.messages_repository.update(message, item_id=message_id)
            await self.transaction.commit()
            # Returned from inside the block, right after commit(): __aexit__ then sees no open
            # transaction (commit ended it) and only closes the session - it does not roll back,
            # so `updated`'s already-loaded attributes (no relationships here to eager-load) stay
            # usable for the caller.
            return updated
