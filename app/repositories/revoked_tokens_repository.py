import datetime as dt

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy.dialects import postgresql

from app.database import tables


class RevokedTokensRepository(SQLAlchemyAsyncRepositoryService[tables.RevokedTokensTable]):
    class BaseRepository(SQLAlchemyAsyncRepository[tables.RevokedTokensTable]):
        model_type = tables.RevokedTokensTable
        id_attribute = "jti"

    repository_type = BaseRepository

    async def is_revoked(self, jti: str) -> bool:
        return await self.exists(jti=jti)

    async def revoke(self, jti: str, expires_at: dt.datetime) -> None:
        await self.repository.session.execute(
            postgresql.insert(tables.RevokedTokensTable)
            .values(jti=jti, expires_at=expires_at)
            .on_conflict_do_nothing(index_elements=[tables.RevokedTokensTable.jti])
        )

    async def prune_expired(self, now: dt.datetime) -> None:
        await self.delete_where(tables.RevokedTokensTable.expires_at < now)
