import dataclasses
import datetime

from db_retry import Transaction, postgres_retry

from app.database import tables
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.messages_repository import MessagesRepository
from app.use_cases.message_authorization import fetch_message_for_author


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class DeleteMessageUseCase:
    transaction: Transaction
    messages_repository: MessagesRepository
    chat_members_repository: ChatMembersRepository

    @postgres_retry
    async def __call__(self, actor: tables.UsersTable, message_id: int) -> None:
        async with self.transaction:
            message = await fetch_message_for_author(
                messages_repository=self.messages_repository,
                chat_members_repository=self.chat_members_repository,
                actor=actor,
                message_id=message_id,
                action="delete",
            )
            if message.deleted_at is not None:
                # DELETE is idempotent under HTTP semantics: a second delete of an
                # already-deleted message is not an error, unlike PATCH via EditMessageUseCase.
                return
            message.deleted_at = datetime.datetime.now(tz=datetime.UTC)
            await self.messages_repository.update(message, item_id=message_id)
            await self.transaction.commit()
