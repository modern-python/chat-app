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
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].unread_count == 2


async def test_own_messages_are_never_unread(
    fetch_chats_use_case: FetchChatsUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    send: SendFixture,
) -> None:
    await send(alice, direct_chat.id, "mine")
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].unread_count == 0


async def test_system_messages_count_as_unread(
    fetch_chats_use_case: FetchChatsUseCase,
    messages_repository: MessagesRepository,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
) -> None:
    await messages_repository.create(
        tables.MessagesTable(chat_id=direct_chat.id, user_id=None, idempotency_key=uuid.uuid4(), text="Bob joined")
    )
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].unread_count == 1


async def test_marking_read_clears_the_count(
    fetch_chats_use_case: FetchChatsUseCase,
    mark_read_use_case: MarkReadUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    message, _ = await send(bob, direct_chat.id, "one")
    await mark_read_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.MarkReadRequest(last_read_message_id=message.id)
    )
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].unread_count == 0


async def test_deleted_messages_are_not_unread(
    fetch_chats_use_case: FetchChatsUseCase,
    delete_message_use_case: DeleteMessageUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    message, _ = await send(bob, direct_chat.id, "one")
    await delete_message_use_case(actor=bob, message_id=message.id)
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].unread_count == 0


async def test_chat_with_no_messages_has_no_last_message(
    fetch_chats_use_case: FetchChatsUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].id == direct_chat.id
    assert chats[0].last_message is None
    assert chats[0].unread_count == 0


async def test_listing_orders_most_recently_active_chat_first(
    fetch_chats_use_case: FetchChatsUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    carol: tables.UsersTable,
    send: SendFixture,
) -> None:
    other_chat, _ = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    await send(alice, direct_chat.id, "first chat gets a message")
    chats = await fetch_chats_use_case(actor=alice)
    assert [chat.id for chat in chats] == [direct_chat.id, other_chat.id]


async def test_unread_counts_differ_per_chat(
    fetch_chats_use_case: FetchChatsUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    carol: tables.UsersTable,
    send: SendFixture,
) -> None:
    other_chat, _ = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    await send(bob, direct_chat.id, "one")
    await send(bob, direct_chat.id, "two")
    await send(carol, other_chat.id, "hi")

    chats = await fetch_chats_use_case(actor=alice)

    counts = {chat.id: chat.unread_count for chat in chats}
    assert counts == {direct_chat.id: 2, other_chat.id: 1}


async def test_non_member_cannot_mark_read(
    mark_read_use_case: MarkReadUseCase, direct_chat: tables.ChatsTable, carol: tables.UsersTable
) -> None:
    with pytest.raises(PermissionDeniedError):
        await mark_read_use_case(
            actor=carol, chat_id=direct_chat.id, data=schemas.MarkReadRequest(last_read_message_id=1)
        )


async def test_marking_read_with_a_message_from_another_chat_is_rejected(
    mark_read_use_case: MarkReadUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    carol: tables.UsersTable,
    send: SendFixture,
) -> None:
    other_chat, _ = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    other_message, _ = await send(alice, other_chat.id, "elsewhere")
    with pytest.raises(ValidationError):
        await mark_read_use_case(
            actor=alice, chat_id=direct_chat.id, data=schemas.MarkReadRequest(last_read_message_id=other_message.id)
        )


async def test_marking_read_rejects_an_unknown_message_id(
    mark_read_use_case: MarkReadUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    with pytest.raises(ValidationError):
        await mark_read_use_case(
            actor=alice, chat_id=direct_chat.id, data=schemas.MarkReadRequest(last_read_message_id=999999)
        )


async def test_marking_read_is_monotonic(
    fetch_chats_use_case: FetchChatsUseCase,
    mark_read_use_case: MarkReadUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    send: SendFixture,
) -> None:
    first, _ = await send(bob, direct_chat.id, "one")
    second, _ = await send(bob, direct_chat.id, "two")
    await mark_read_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.MarkReadRequest(last_read_message_id=second.id)
    )

    member = await mark_read_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.MarkReadRequest(last_read_message_id=first.id)
    )

    assert member.last_read_message_id == second.id
    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].unread_count == 0


async def test_deleting_the_newest_message_updates_preview_and_ordering(
    fetch_chats_use_case: FetchChatsUseCase,
    delete_message_use_case: DeleteMessageUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    carol: tables.UsersTable,
    send: SendFixture,
) -> None:
    other_chat, _ = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    await send(alice, direct_chat.id, "direct chat message")
    newest, _ = await send(alice, other_chat.id, "other chat message")

    before = await fetch_chats_use_case(actor=alice)
    assert [chat.id for chat in before] == [other_chat.id, direct_chat.id]

    await delete_message_use_case(actor=alice, message_id=newest.id)

    after = await fetch_chats_use_case(actor=alice)
    assert [chat.id for chat in after] == [direct_chat.id, other_chat.id]
    listed_other_chat = next(chat for chat in after if chat.id == other_chat.id)
    assert listed_other_chat.last_message is None
    assert listed_other_chat.last_message_id is None


async def test_deleting_a_non_newest_message_leaves_preview_and_ordering_unchanged(
    fetch_chats_use_case: FetchChatsUseCase,
    delete_message_use_case: DeleteMessageUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    send: SendFixture,
) -> None:
    first, _ = await send(alice, direct_chat.id, "first")
    second, _ = await send(alice, direct_chat.id, "second")

    await delete_message_use_case(actor=alice, message_id=first.id)

    chats = await fetch_chats_use_case(actor=alice)
    assert chats[0].last_message_id == second.id
    assert chats[0].last_message is not None
    assert chats[0].last_message.id == second.id
