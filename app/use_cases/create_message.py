import dataclasses
import typing

from advanced_alchemy.exceptions import DuplicateKeyError
from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas.api import SendMessageRequest


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class CreateMessageUseCase:
    transaction: Transaction
    chats_repository: ChatsRepository
    chat_members_repository: ChatMembersRepository
    messages_repository: MessagesRepository

    @postgres_retry
    async def __call__(
        self, *, actor: Actor, chat_id: int, data: SendMessageRequest
    ) -> tuple[tables.MessagesTable, bool]:
        if not await self.chat_members_repository.is_member(chat_id, actor.id):
            msg = "Not a member of this chat"
            raise PermissionDeniedError(msg)

        existing: typing.Final = await self.messages_repository.fetch_by_idempotency_key(chat_id, data.idempotency_key)
        if existing is not None:
            return existing, False

        message: tables.MessagesTable | None = None
        async with self.transaction:
            try:
                message = await self.messages_repository.create(
                    tables.MessagesTable(
                        chat_id=chat_id,
                        user_id=actor.id,
                        idempotency_key=data.idempotency_key,
                        text=data.text,
                    )
                )
            except DuplicateKeyError:
                # Re-read outside the block: __aexit__ rolls back and detaches on an open transaction.
                await self.transaction.rollback()
            else:
                await self.chats_repository.update(
                    tables.ChatsTable(id=chat_id, last_message_id=message.id),
                    item_id=chat_id,
                    attribute_names=["last_message_id"],
                )
                await self.transaction.commit()

        if message is None:
            duplicate = await self.messages_repository.fetch_by_idempotency_key(chat_id, data.idempotency_key)
            if duplicate is None:
                msg = "Message send raced but the resulting row could not be found"
                raise RuntimeError(msg)
            return duplicate, False

        return message, True
