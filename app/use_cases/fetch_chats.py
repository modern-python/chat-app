import dataclasses
import typing

from db_retry import postgres_retry

from app.database import tables
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository


@dataclasses.dataclass(frozen=True, slots=True)
class ChatListRow:
    chat: tables.ChatsTable
    unread_count: int
    last_message: tables.MessagesTable | None


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchChatsUseCase:
    chats_repository: ChatsRepository
    messages_repository: MessagesRepository

    @postgres_retry
    async def __call__(self, actor: tables.UsersTable) -> list[ChatListRow]:
        rows: typing.Final = await self.chats_repository.list_for_user(actor.id)

        # One bounded lookup for every chat's last message, not one query per row: collect the
        # non-null last_message_id values and load them with a single WHERE id IN (...).
        last_message_ids: typing.Final = {row[0].last_message_id for row in rows if row[0].last_message_id is not None}
        last_messages: dict[int, tables.MessagesTable] = {}
        if last_message_ids:
            # deleted_at.is_(None) is a self-defending guard, not the source of truth: DeleteMessageUseCase
            # repoints chats.last_message_id off a deleted message in the same commit as the soft delete,
            # so this filter should never actually exclude anything - it just keeps this query correct on
            # its own if another write path ever sets the column without doing that.
            messages = await self.messages_repository.get_many(
                tables.MessagesTable.id.in_(last_message_ids), tables.MessagesTable.deleted_at.is_(None)
            )
            last_messages = {message.id: message for message in messages}

        return [
            ChatListRow(
                chat=row[0],
                unread_count=row.unread_count,
                last_message=last_messages.get(row[0].last_message_id) if row[0].last_message_id is not None else None,
            )
            for row in rows
        ]
