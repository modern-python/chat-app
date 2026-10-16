import dataclasses
import typing
from collections.abc import Sequence

from db_retry import Transaction, postgres_retry

from app.actor import Actor
from app.database import tables
from app.repositories.chats_repository import ChatsRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchChatsUseCase:
    transaction: Transaction
    chats_repository: ChatsRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor) -> Sequence[tables.ChatsTable]:
        async with self.transaction:
            chats: typing.Final = await self.chats_repository.list_for_user(actor.id)
            await self.transaction.commit()
        return chats
