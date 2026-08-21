import dataclasses
import typing
from collections.abc import Sequence

from db_retry import postgres_retry

from app.database import tables
from app.exceptions import PermissionDeniedError, ValidationError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.messages_repository import MessagesRepository


MAX_PAGE_SIZE: typing.Final = 100


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class FetchMessagesUseCase:
    chat_members_repository: ChatMembersRepository
    messages_repository: MessagesRepository

    @postgres_retry
    async def __call__(
        self,
        actor: tables.UsersTable,
        chat_id: int,
        *,
        before_id: int | None = None,
        after_id: int | None = None,
        limit: int = 50,
    ) -> Sequence[tables.MessagesTable]:
        if not await self.chat_members_repository.is_member(chat_id, actor.id):
            msg = "Not a member of this chat"
            raise PermissionDeniedError(msg)
        if before_id is not None and after_id is not None:
            msg = "before_id and after_id are mutually exclusive"
            raise ValidationError(msg)
        if limit < 1:
            msg = "limit must be at least 1"
            raise ValidationError(msg)
        return await self.messages_repository.list_page(
            chat_id, before_id=before_id, after_id=after_id, limit=min(limit, MAX_PAGE_SIZE)
        )
