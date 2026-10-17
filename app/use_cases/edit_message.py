import dataclasses
import datetime as dt

from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.database import tables
from app.exceptions import ConflictError
from app.repositories.messages_repository import MessagesRepository
from app.schemas.api import EditMessageRequest
from app.use_cases.message_authorization import fetch_message_for_author


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class EditMessageUseCase:
    transaction: Transaction
    messages_repository: MessagesRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor, message_id: int, data: EditMessageRequest) -> tables.MessagesTable:
        async with self.transaction:
            message = await fetch_message_for_author(
                messages_repository=self.messages_repository,
                actor=actor,
                message_id=message_id,
                action="edit",
            )
            if message.deleted_at is not None:
                msg = "This message has been deleted"
                raise ConflictError(msg)
            updated = await self.messages_repository.edit_text(message_id, data.text, dt.datetime.now(tz=dt.UTC))
            await self.transaction.commit()
            # Safe inside the block: commit() ended the transaction, so __aexit__ only closes.
            return updated
