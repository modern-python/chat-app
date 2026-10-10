import dataclasses

from db_retry import postgres_retry

from app.repositories.revoked_tokens_repository import RevokedTokensRepository


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class CheckTokenRevokedUseCase:
    revoked_tokens_repository: RevokedTokensRepository

    @postgres_retry
    async def __call__(self, *, jti: str) -> bool:
        return await self.revoked_tokens_repository.is_revoked(jti)
