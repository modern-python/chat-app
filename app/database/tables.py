import datetime
import enum
import typing
import uuid

import sqlalchemy as sa
from advanced_alchemy.base import BigIntAuditBase, BigIntBase, orm_registry
from advanced_alchemy.types import GUID, DateTimeUTC
from sqlalchemy import orm


METADATA: typing.Final = orm_registry.metadata
orm.DeclarativeBase.metadata = METADATA


class UsersTable(BigIntAuditBase):
    __tablename__ = "users"

    username: orm.Mapped[str] = orm.mapped_column(sa.String(length=64), unique=True)
    password_hash: orm.Mapped[str] = orm.mapped_column(sa.String)
    display_name: orm.Mapped[str] = orm.mapped_column(sa.String(length=128))


class ChatType(enum.StrEnum):
    DIRECT = "direct"
    GROUP = "group"


def build_direct_key(user_id_a: int, user_id_b: int) -> str:
    """Order-independent identity for a direct chat between two users."""
    low, high = sorted((user_id_a, user_id_b))
    return f"{low}:{high}"


class ChatsTable(BigIntAuditBase):
    __tablename__ = "chats"

    chat_type: orm.Mapped[ChatType] = orm.mapped_column(
        sa.Enum(
            ChatType,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    title: orm.Mapped[str | None] = orm.mapped_column(sa.String(length=128), nullable=True)
    created_by_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"))
    last_message_id: orm.Mapped[int | None] = orm.mapped_column(sa.BigInteger, nullable=True)
    direct_key: orm.Mapped[str | None] = orm.mapped_column(sa.String(length=64), nullable=True, unique=True)

    members: orm.Mapped[list[ChatMembersTable]] = orm.relationship(
        "ChatMembersTable", lazy="noload", uselist=True, viewonly=True
    )


class ChatMembersTable(BigIntBase):
    __tablename__ = "chat_members"
    __table_args__ = (sa.UniqueConstraint("chat_id", "user_id", name="uk_chat_members_chat_id_user_id"),)

    chat_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("chats.id"))
    user_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("users.id"), index=True)
    last_read_message_id: orm.Mapped[int | None] = orm.mapped_column(sa.BigInteger, nullable=True)
    joined_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        DateTimeUTC(timezone=True), default=lambda: datetime.datetime.now(tz=datetime.UTC)
    )


class MessagesTable(BigIntBase):
    __tablename__ = "messages"
    __table_args__ = (sa.Index("ix_messages_chat_id_id", "chat_id", "id"),)

    # No standalone index on chat_id: the (chat_id, id) composite index below already serves
    # every query that would use one.
    chat_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("chats.id"))
    user_id: orm.Mapped[int | None] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=True, index=True)
    idempotency_key: orm.Mapped[uuid.UUID] = orm.mapped_column(GUID, unique=True)
    text: orm.Mapped[str] = orm.mapped_column(sa.String)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        DateTimeUTC(timezone=True), default=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    edited_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(DateTimeUTC(timezone=True), nullable=True)
    deleted_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(DateTimeUTC(timezone=True), nullable=True)
