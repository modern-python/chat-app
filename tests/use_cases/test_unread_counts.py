import typing
import uuid

import pytest

from app.database import tables
from app.exceptions import PermissionDeniedError, ValidationError
from app.repositories.messages_repository import MessagesRepository
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.delete_message import DeleteMessageUseCase
from app.use_cases.fetch_chats import FetchChatsUseCase
from app.use_cases.mark_read import MarkReadUseCase


SendFixture = typing.Callable[[tables.UsersTable, int, str], typing.Awaitable[tuple[tables.MessagesTable, bool]]]


async def test_unread_counts_messages_from_others(
    fetch_chats_use_case: FetchChatsUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    await send(bob, direct_chat.id, "one")
    await send(bob, direct_chat.id, "two")
    rows = await fetch_chats_use_case(alice)
    assert rows[0].unread_count == 2


async def test_own_messages_are_never_unread(
    fetch_chats_use_case: FetchChatsUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    send: SendFixture,
) -> None:
    await send(alice, direct_chat.id, "mine")
    rows = await fetch_chats_use_case(alice)
    assert rows[0].unread_count == 0


async def test_system_messages_count_as_unread(
    fetch_chats_use_case: FetchChatsUseCase,
    messages_repository: MessagesRepository,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
) -> None:
    await messages_repository.create(
        tables.MessagesTable(chat_id=direct_chat.id, user_id=None, idempotency_key=uuid.uuid4(), text="Bob joined")
    )
    rows = await fetch_chats_use_case(alice)
    assert rows[0].unread_count == 1


async def test_marking_read_clears_the_count(  # noqa: PLR0913, PLR0917 - each is a fixture-injected dependency
    fetch_chats_use_case: FetchChatsUseCase,
    mark_read_use_case: MarkReadUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    message, _ = await send(bob, direct_chat.id, "one")
    await mark_read_use_case(alice, direct_chat.id, schemas.MarkReadRequest(last_read_message_id=message.id))
    rows = await fetch_chats_use_case(alice)
    assert rows[0].unread_count == 0


async def test_deleted_messages_are_not_unread(  # noqa: PLR0913, PLR0917 - each is a fixture-injected dependency
    fetch_chats_use_case: FetchChatsUseCase,
    delete_message_use_case: DeleteMessageUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    message, _ = await send(bob, direct_chat.id, "one")
    await delete_message_use_case(bob, message.id)
    rows = await fetch_chats_use_case(alice)
    assert rows[0].unread_count == 0


async def test_chat_with_no_messages_has_no_last_message(
    fetch_chats_use_case: FetchChatsUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    rows = await fetch_chats_use_case(alice)
    assert rows[0].chat.id == direct_chat.id
    assert rows[0].last_message is None
    assert rows[0].unread_count == 0


async def test_listing_orders_most_recently_active_chat_first(  # noqa: PLR0913, PLR0917 - fixture-injected
    fetch_chats_use_case: FetchChatsUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    carol: tables.UsersTable,
    send: SendFixture,
) -> None:
    other_chat, _ = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    await send(alice, direct_chat.id, "first chat gets a message")
    rows = await fetch_chats_use_case(alice)
    assert [row.chat.id for row in rows] == [direct_chat.id, other_chat.id]


async def test_listing_only_includes_the_callers_chats(
    fetch_chats_use_case: FetchChatsUseCase,
    direct_chat: tables.ChatsTable,
    carol: tables.UsersTable,
) -> None:
    rows = await fetch_chats_use_case(carol)
    assert direct_chat.id not in [row.chat.id for row in rows]


async def test_non_member_cannot_mark_read(
    mark_read_use_case: MarkReadUseCase, direct_chat: tables.ChatsTable, carol: tables.UsersTable
) -> None:
    with pytest.raises(PermissionDeniedError):
        await mark_read_use_case(carol, direct_chat.id, schemas.MarkReadRequest(last_read_message_id=1))


async def test_marking_read_with_a_message_from_another_chat_is_rejected(  # noqa: PLR0913, PLR0917 - fixture-injected
    mark_read_use_case: MarkReadUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    carol: tables.UsersTable,
    send: SendFixture,
) -> None:
    other_chat, _ = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    other_message, _ = await send(alice, other_chat.id, "elsewhere")
    with pytest.raises(ValidationError):
        await mark_read_use_case(alice, direct_chat.id, schemas.MarkReadRequest(last_read_message_id=other_message.id))


async def test_marking_read_rejects_an_unknown_message_id(
    mark_read_use_case: MarkReadUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    with pytest.raises(ValidationError):
        await mark_read_use_case(alice, direct_chat.id, schemas.MarkReadRequest(last_read_message_id=999999))


async def test_marking_read_is_monotonic(  # noqa: PLR0913, PLR0917 - each is a fixture-injected dependency
    fetch_chats_use_case: FetchChatsUseCase,
    mark_read_use_case: MarkReadUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    first, _ = await send(bob, direct_chat.id, "one")
    second, _ = await send(bob, direct_chat.id, "two")
    await mark_read_use_case(alice, direct_chat.id, schemas.MarkReadRequest(last_read_message_id=second.id))

    # An out-of-order/replayed request naming an earlier message must not move the marker back.
    member = await mark_read_use_case(alice, direct_chat.id, schemas.MarkReadRequest(last_read_message_id=first.id))

    assert member.last_read_message_id == second.id
    rows = await fetch_chats_use_case(alice)
    assert rows[0].unread_count == 0
