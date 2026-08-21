import uuid

import pytest

from app.database import tables
from app.exceptions import ConflictError, PermissionDeniedError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas import api as schemas
from app.use_cases.create_message import CreateMessageUseCase
from app.use_cases.delete_message import DeleteMessageUseCase
from app.use_cases.edit_message import EditMessageUseCase
from app.use_cases.fetch_messages import FetchMessagesUseCase


async def test_author_can_edit(
    edit_message_use_case: EditMessageUseCase, alice_message: tables.MessagesTable, alice: tables.UsersTable
) -> None:
    edited = await edit_message_use_case(
        actor=alice, message_id=alice_message.id, data=schemas.EditMessageRequest(text="fixed")
    )
    assert edited.text == "fixed"
    assert edited.edited_at is not None


async def test_other_member_cannot_edit(
    edit_message_use_case: EditMessageUseCase, alice_message: tables.MessagesTable, bob: tables.UsersTable
) -> None:
    # bob is a member of the chat, not the author - membership alone must not authorize the edit.
    with pytest.raises(PermissionDeniedError):
        await edit_message_use_case(
            actor=bob, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def _remove_alice_from_chat(
    chat_members_repository: ChatMembersRepository, alice_message: tables.MessagesTable, alice: tables.UsersTable
) -> None:
    membership = await chat_members_repository.get_one(chat_id=alice_message.chat_id, user_id=alice.id)
    await chat_members_repository.delete(item_id=membership.id)


async def test_author_without_membership_cannot_edit(
    edit_message_use_case: EditMessageUseCase,
    chat_members_repository: ChatMembersRepository,
    alice_message: tables.MessagesTable,
    alice: tables.UsersTable,
) -> None:
    # alice is still the message's author but no longer a member of its chat (e.g. removed) -
    # the one state where authorship and membership disagree, and the only state that can prove
    # the membership check does anything the authorship check doesn't already cover.
    await _remove_alice_from_chat(chat_members_repository, alice_message, alice)
    with pytest.raises(PermissionDeniedError):
        await edit_message_use_case(
            actor=alice, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def test_non_member_cannot_edit(
    edit_message_use_case: EditMessageUseCase, alice_message: tables.MessagesTable, carol: tables.UsersTable
) -> None:
    # carol isn't in direct_chat at all - the membership gate must refuse her before authorship
    # is even considered.
    with pytest.raises(PermissionDeniedError):
        await edit_message_use_case(
            actor=carol, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def test_editing_a_deleted_message_raises_conflict(
    edit_message_use_case: EditMessageUseCase,
    delete_message_use_case: DeleteMessageUseCase,
    alice_message: tables.MessagesTable,
    alice: tables.UsersTable,
) -> None:
    # The author is authorized; the request conflicts with the message's current state, so this
    # is a 409-shaped ConflictError, not a 403-shaped PermissionDeniedError.
    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    with pytest.raises(ConflictError):
        await edit_message_use_case(
            actor=alice, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def test_author_can_delete(
    delete_message_use_case: DeleteMessageUseCase,
    messages_repository: MessagesRepository,
    alice_message: tables.MessagesTable,
    alice: tables.UsersTable,
) -> None:
    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    stored = await messages_repository.get_one(id=alice_message.id)
    assert stored.deleted_at is not None


async def test_other_member_cannot_delete(
    delete_message_use_case: DeleteMessageUseCase, alice_message: tables.MessagesTable, bob: tables.UsersTable
) -> None:
    # Same distinction as edit: bob is a member of the chat but not the author.
    with pytest.raises(PermissionDeniedError):
        await delete_message_use_case(actor=bob, message_id=alice_message.id)


async def test_author_without_membership_cannot_delete(
    delete_message_use_case: DeleteMessageUseCase,
    chat_members_repository: ChatMembersRepository,
    alice_message: tables.MessagesTable,
    alice: tables.UsersTable,
) -> None:
    # Same distinction as edit.
    await _remove_alice_from_chat(chat_members_repository, alice_message, alice)
    with pytest.raises(PermissionDeniedError):
        await delete_message_use_case(actor=alice, message_id=alice_message.id)


async def test_non_member_cannot_delete(
    delete_message_use_case: DeleteMessageUseCase, alice_message: tables.MessagesTable, carol: tables.UsersTable
) -> None:
    # Same distinction as edit: carol isn't in direct_chat at all.
    with pytest.raises(PermissionDeniedError):
        await delete_message_use_case(actor=carol, message_id=alice_message.id)


async def test_deleting_an_already_deleted_message_is_idempotent(
    delete_message_use_case: DeleteMessageUseCase,
    messages_repository: MessagesRepository,
    alice_message: tables.MessagesTable,
    alice: tables.UsersTable,
) -> None:
    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    first_deleted_at = (await messages_repository.get_one(id=alice_message.id)).deleted_at

    await delete_message_use_case(actor=alice, message_id=alice_message.id)

    stored = await messages_repository.get_one(id=alice_message.id)
    assert stored.deleted_at == first_deleted_at


async def test_deleted_message_disappears_from_listing(
    delete_message_use_case: DeleteMessageUseCase,
    fetch_messages_use_case: FetchMessagesUseCase,
    create_message_use_case: CreateMessageUseCase,
    alice_message: tables.MessagesTable,
    alice: tables.UsersTable,
) -> None:
    # A second, undeleted message proves the listing filters *deleted* messages specifically -
    # an empty result here would prove nothing, since the chat would just be empty either way.
    other, _ = await create_message_use_case(
        actor=alice,
        chat_id=alice_message.chat_id,
        data=schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="still here"),
    )

    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    page = await fetch_messages_use_case(actor=alice, chat_id=alice_message.chat_id)

    assert [message.id for message in page] == [other.id]
