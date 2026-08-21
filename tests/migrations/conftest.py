import typing

import pytest
from sqlalchemy import Engine, create_engine

from app.settings import settings


@pytest.fixture
def alembic_engine() -> typing.Iterator[Engine]:
    # Overrides pytest-alembic's default in-memory SQLite engine: these tests are only
    # meaningful against the Postgres the migrations actually target.
    engine: typing.Final = create_engine(settings.sync_db_dsn_parsed)
    yield engine
    engine.dispose()
