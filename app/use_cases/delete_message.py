import dataclasses
import datetime as dt

from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.use_cases.message_authorization import fetch_message_for_author


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class DeleteMessageUseCase:
    transaction: Transaction
    messages_repository: MessagesRepository
    chats_repository: ChatsRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor, message_id: int) -> None:
        async with self.transaction:
            message = await fetch_message_for_author(
                messages_repository=self.messages_repository,
                actor=actor,
                message_id=message_id,
                action="delete",
            )
            if message.deleted_at is not None:
                # DELETE is idempotent; a second delete is not an error, unlike an edit.
                return
            await self.messages_repository.soft_delete(message_id, dt.datetime.now(tz=dt.UTC))
            await self.chats_repository.repoint_last_message(message.chat_id, message_id)
            await self.transaction.commit()
