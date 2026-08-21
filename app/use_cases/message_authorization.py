import typing

from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.messages_repository import MessagesRepository


async def fetch_message_for_author(
    *,
    messages_repository: MessagesRepository,
    chat_members_repository: ChatMembersRepository,
    actor: tables.UsersTable,
    message_id: int,
    action: str,
) -> tables.MessagesTable:
    """Look up a message and authorize `actor` to act on it as its author.

    Shared by EditMessageUseCase and DeleteMessageUseCase so the check ordering is defined in
    exactly one place: existence (get_one raises NotFoundError -> 404), then chat membership
    (-> 403), then authorship (-> 403). Membership is checked even though a non-author is
    already refused by the authorship check below - mirroring FetchMessagesUseCase's and
    FetchChatUseCase's membership-first posture keeps this consistent with the rest of the
    codebase rather than leaving message mutation as the one actor-scoped use case that never
    reconfirms the actor still belongs to the chat.
    """
    message: typing.Final = await messages_repository.get_one(id=message_id)
    if not await chat_members_repository.is_member(message.chat_id, actor.id):
        msg = "Not a member of this chat"
        raise PermissionDeniedError(msg)
    if message.user_id != actor.id:
        msg = f"Only the author may {action} this message"
        raise PermissionDeniedError(msg)
    return message
