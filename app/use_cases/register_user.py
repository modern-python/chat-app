import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app import security
from app.database import tables
from app.repositories.users_repository import UsersRepository
from app.schemas.api import RegisterRequest


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class RegisterUserUseCase:
    transaction: Transaction
    users_repository: UsersRepository

    @postgres_retry
    async def __call__(self, *, data: RegisterRequest) -> tables.UsersTable:
        async with self.transaction:
            user: typing.Final = await self.users_repository.create(
                tables.UsersTable(
                    username=data.username,
                    password_hash=security.hash_password(data.password),
                    display_name=data.display_name,
                )
            )
            await self.transaction.commit()
            return user
