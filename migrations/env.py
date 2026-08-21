from logging.config import fileConfig

from alembic import context
from sqlalchemy import URL, create_engine

from app.database.tables import METADATA
from app.settings import settings


def get_dsn() -> URL:
    return settings.db_dsn_parsed.set(drivername="postgresql")


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = METADATA


def run_migrations_offline() -> None:
    context.configure(
        url=get_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_dsn())
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():  # pragma: no cover
    run_migrations_offline()
else:
    run_migrations_online()
