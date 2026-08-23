import dataclasses
from collections.abc import Sequence

from db_retry import postgres_retry

from app.actor import Actor
from app.database import tables
from app.repositories.chats_repository import ChatsRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchChatsUseCase:
    chats_repository: ChatsRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor) -> Sequence[tables.ChatsTable]:
        return await self.chats_repository.list_for_user(actor.id)
