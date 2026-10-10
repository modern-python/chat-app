import datetime as dt

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import tables
from app.use_cases.check_token_revoked import CheckTokenRevokedUseCase
from app.use_cases.revoke_token import RevokeTokenUseCase


async def test_revoke_prunes_expired_rows(revoke_token_use_case: RevokeTokenUseCase, db_session: AsyncSession) -> None:
    now = dt.datetime.now(tz=dt.UTC)
    await revoke_token_use_case(jti="expired", expires_at=now - dt.timedelta(seconds=1))
    await revoke_token_use_case(jti="live", expires_at=now + dt.timedelta(hours=1))
    stored = await db_session.scalars(sa.select(tables.RevokedTokensTable.jti))
    assert stored.all() == ["live"]


async def test_revoking_twice_is_a_no_op(
    revoke_token_use_case: RevokeTokenUseCase, check_token_revoked_use_case: CheckTokenRevokedUseCase
) -> None:
    expires_at = dt.datetime.now(tz=dt.UTC) + dt.timedelta(hours=1)
    await revoke_token_use_case(jti="twice", expires_at=expires_at)
    await revoke_token_use_case(jti="twice", expires_at=expires_at)
    assert await check_token_revoked_use_case(jti="twice")
