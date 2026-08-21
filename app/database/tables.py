import typing

import sqlalchemy as sa
from advanced_alchemy.base import BigIntAuditBase, orm_registry
from sqlalchemy import orm


METADATA: typing.Final = orm_registry.metadata
orm.DeclarativeBase.metadata = METADATA


class UsersTable(BigIntAuditBase):
    __tablename__ = "users"

    username: orm.Mapped[str] = orm.mapped_column(sa.String(length=64), unique=True)
    password_hash: orm.Mapped[str] = orm.mapped_column(sa.String)
    display_name: orm.Mapped[str] = orm.mapped_column(sa.String(length=128))
