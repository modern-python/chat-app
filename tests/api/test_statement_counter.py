import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.resources import create_database_engine
from tests.api.helpers import count_statements as _count_statements


async def test_count_statements_ignores_other_connections(db_session: AsyncSession) -> None:
    engine = create_database_engine()
    try:
        with _count_statements(db_session) as statements:
            async with engine.connect() as other_connection:
                await other_connection.execute(sa.text("SELECT 1"))
            await db_session.execute(sa.text("SELECT 2"))
    finally:
        await engine.dispose()

    assert "SELECT 1" not in statements
    assert "SELECT 2" in statements
