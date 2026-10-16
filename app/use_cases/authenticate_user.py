import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app import security
from app.database import tables
from app.repositories.users_repository import UsersRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class AuthenticateUserUseCase:
    transaction: Transaction
    users_repository: UsersRepository

    @postgres_retry
    async def __call__(self, *, username: str, password: str) -> tables.UsersTable | None:
        async with self.transaction:
            user: typing.Final = await self.users_repository.get_one_or_none(username=username)
            await self.transaction.commit()
        if user is None:
            # Discarded, but skipping the argon2 work would turn login timing into a username oracle.
            security.hash_password(password)
            return None
        if not security.verify_password(user.password_hash, password):
            return None
        return user
