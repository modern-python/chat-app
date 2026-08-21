import dataclasses
import datetime

from db_retry import Transaction, postgres_retry

from app.database import tables
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.use_cases.message_authorization import fetch_message_for_author


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class DeleteMessageUseCase:
    transaction: Transaction
    messages_repository: MessagesRepository
    chat_members_repository: ChatMembersRepository
    chats_repository: ChatsRepository

    @postgres_retry
    async def __call__(self, *, actor: tables.UsersTable, message_id: int) -> None:
        async with self.transaction:
            message = await fetch_message_for_author(
                messages_repository=self.messages_repository,
                chat_members_repository=self.chat_members_repository,
                actor=actor,
                message_id=message_id,
                action="delete",
            )
            if message.deleted_at is not None:
                # DELETE is idempotent; a second delete is not an error, unlike an edit.
                return
            message.deleted_at = datetime.datetime.now(tz=datetime.UTC)
            await self.messages_repository.update(message, item_id=message_id)

            chat = await self.chats_repository.get_one(id=message.chat_id)
            if chat.last_message_id == message_id:
                newest = await self.messages_repository.fetch_latest_active(message.chat_id)
                await self.chats_repository.update(
                    tables.ChatsTable(id=message.chat_id, last_message_id=newest.id if newest is not None else None),
                    item_id=message.chat_id,
                    attribute_names=["last_message_id"],
                )
            await self.transaction.commit()
