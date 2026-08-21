import dataclasses
import typing

from db_retry import postgres_retry

from app import security
from app.database import tables
from app.repositories.users_repository import UsersRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class AuthenticateUserUseCase:
    users_repository: UsersRepository

    @postgres_retry
    async def __call__(self, username: str, password: str) -> tables.UsersTable | None:
        user: typing.Final = await self.users_repository.get_one_or_none(username=username)
        if user is None:
            # Hash anyway: skipping the argon2 work on an unknown username makes the
            # response measurably faster and turns login into a username oracle.
            security.hash_password(password)
            return None
        if not security.verify_password(user.password_hash, password):
            return None
        return user
