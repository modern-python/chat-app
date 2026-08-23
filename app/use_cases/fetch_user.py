import dataclasses

from db_retry import postgres_retry

from app.actor import Actor
from app.database import tables
from app.repositories.users_repository import UsersRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchUserUseCase:
    users_repository: UsersRepository

    @postgres_retry
    async def __call__(self, *, actor: Actor) -> tables.UsersTable | None:
        return await self.users_repository.get_one_or_none(id=actor.id)
