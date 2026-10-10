import dataclasses
import datetime as dt

from db_retry import Transaction, postgres_retry

from app.repositories.revoked_tokens_repository import RevokedTokensRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class RevokeTokenUseCase:
    transaction: Transaction
    revoked_tokens_repository: RevokedTokensRepository

    @postgres_retry
    async def __call__(self, *, jti: str, expires_at: dt.datetime) -> None:
        async with self.transaction:
            await self.revoked_tokens_repository.prune_expired(dt.datetime.now(tz=dt.UTC))
            await self.revoked_tokens_repository.revoke(jti, expires_at)
            await self.transaction.commit()
