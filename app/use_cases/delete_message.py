import dataclasses
import datetime
import typing

from db_retry import Transaction, postgres_retry

from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.messages_repository import MessagesRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class DeleteMessageUseCase:
    transaction: Transaction
    messages_repository: MessagesRepository

    @postgres_retry
    async def __call__(self, actor: tables.UsersTable, message_id: int) -> None:
        async with self.transaction:
            message: typing.Final = await self.messages_repository.get_one(id=message_id)
            if message.user_id != actor.id:
                msg = "Only the author may delete this message"
                raise PermissionDeniedError(msg)
            if message.deleted_at is not None:
                # DELETE is idempotent under HTTP semantics: a second delete of an
                # already-deleted message is not an error, unlike PATCH via EditMessageUseCase.
                return
            message.deleted_at = datetime.datetime.now(tz=datetime.UTC)
            await self.messages_repository.update(message, item_id=message_id)
            await self.transaction.commit()
