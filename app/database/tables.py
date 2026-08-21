import datetime
import enum
import typing
import uuid

import sqlalchemy as sa
from advanced_alchemy.base import BigIntAuditBase, BigIntBase, orm_registry
from advanced_alchemy.types import GUID, DateTimeUTC
from sqlalchemy import orm


METADATA: typing.Final = orm_registry.metadata
# Redirects SQLAlchemy's shared declarative base onto advanced-alchemy's registry metadata so
# that every model below - which inherits BigIntAuditBase/BigIntBase, themselves built on
# orm.DeclarativeBase - registers its table on METADATA. Alembic's env.py autogenerates against
# METADATA directly; without this reassignment, models would register on orm.DeclarativeBase's
# own separate metadata instead, and autogen would see no tables at all.
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

    # Per-viewer state that the chat listing needs alongside the chat's own columns. Both are
    # mapped here rather than assembled in Python so that a listed chat is a plain ChatsTable
    # whose attribute names already match the response schema - no per-row DTO, no aliases.
    #
    # unread_count is only populated when the query asks for it via with_expression(); every
    # other query gets default_expr's literal 0, so the attribute is never None.
    unread_count: orm.Mapped[int] = orm.query_expression(default_expr=sa.literal(0))
    # last_message_id deliberately carries no ForeignKey (a chats -> messages FK would close a
    # cycle with messages.chat_id), so the join column has to be annotated foreign() by hand.
    # The soft-delete guard lives in the join rather than at the call site: a chat must never
    # preview a deleted message, whatever loads it. DeleteMessageUseCase still repoints
    # last_message_id in the same commit as the delete - this only keeps the mapping correct on
    # its own if some other write path ever fails to.
    last_message: orm.Mapped[MessagesTable | None] = orm.relationship(
        "MessagesTable",
        primaryjoin=lambda: sa.and_(
            orm.foreign(ChatsTable.last_message_id) == MessagesTable.id,
            MessagesTable.deleted_at.is_(None),
        ),
        lazy="noload",
        uselist=False,
        viewonly=True,
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
    __table_args__ = (
        # No standalone index on chat_id: this composite index already serves every query
        # that would use one.
        sa.Index("ix_messages_chat_id_id", "chat_id", "id"),
        # Idempotency is a property of "send this message to this chat" - two different chats
        # are two different operations, so the key is unique per chat, not table-wide.
        sa.UniqueConstraint("chat_id", "idempotency_key", name="uk_messages_chat_id_idempotency_key"),
    )

    chat_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey("chats.id"))
    user_id: orm.Mapped[int | None] = orm.mapped_column(sa.ForeignKey("users.id"), nullable=True, index=True)
    idempotency_key: orm.Mapped[uuid.UUID] = orm.mapped_column(GUID)
    text: orm.Mapped[str] = orm.mapped_column(sa.String)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        DateTimeUTC(timezone=True), default=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    edited_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(DateTimeUTC(timezone=True), nullable=True)
    deleted_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(DateTimeUTC(timezone=True), nullable=True)
