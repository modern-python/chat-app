import dataclasses
import typing

from db_retry import Transaction, postgres_retry

from app.repositories.revoked_tokens_repository import RevokedTokensRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class CheckTokenRevokedUseCase:
    transaction: Transaction
    revoked_tokens_repository: RevokedTokensRepository

    @postgres_retry
    async def __call__(self, *, jti: str) -> bool:
        async with self.transaction:
            revoked: typing.Final = await self.revoked_tokens_repository.is_revoked(jti)
            await self.transaction.commit()
        return revoked
