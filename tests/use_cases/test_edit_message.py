import uuid

import pytest

from app.actor import Actor
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
    edit_message_use_case: EditMessageUseCase, alice_message: tables.MessagesTable, alice: Actor
) -> None:
    edited = await edit_message_use_case(
        actor=alice, message_id=alice_message.id, data=schemas.EditMessageRequest(text="fixed")
    )
    assert edited.text == "fixed"
    assert edited.edited_at is not None


async def test_other_member_cannot_edit(
    edit_message_use_case: EditMessageUseCase, alice_message: tables.MessagesTable, bob: Actor
) -> None:
    with pytest.raises(PermissionDeniedError):
        await edit_message_use_case(
            actor=bob, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def _remove_alice_from_chat(
    chat_members_repository: ChatMembersRepository, alice_message: tables.MessagesTable, alice: Actor
) -> None:
    membership = await chat_members_repository.get_one(chat_id=alice_message.chat_id, user_id=alice.id)
    await chat_members_repository.delete(item_id=membership.id)


async def test_author_without_membership_cannot_edit(
    edit_message_use_case: EditMessageUseCase,
    chat_members_repository: ChatMembersRepository,
    alice_message: tables.MessagesTable,
    alice: Actor,
) -> None:
    await _remove_alice_from_chat(chat_members_repository, alice_message, alice)
    with pytest.raises(PermissionDeniedError):
        await edit_message_use_case(
            actor=alice, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def test_non_member_cannot_edit(
    edit_message_use_case: EditMessageUseCase, alice_message: tables.MessagesTable, carol: Actor
) -> None:
    with pytest.raises(PermissionDeniedError):
        await edit_message_use_case(
            actor=carol, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def test_editing_a_deleted_message_raises_conflict(
    edit_message_use_case: EditMessageUseCase,
    delete_message_use_case: DeleteMessageUseCase,
    alice_message: tables.MessagesTable,
    alice: Actor,
) -> None:
    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    with pytest.raises(ConflictError):
        await edit_message_use_case(
            actor=alice, message_id=alice_message.id, data=schemas.EditMessageRequest(text="nope")
        )


async def test_author_can_delete(
    delete_message_use_case: DeleteMessageUseCase,
    messages_repository: MessagesRepository,
    alice_message: tables.MessagesTable,
    alice: Actor,
) -> None:
    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    stored = await messages_repository.get_one(id=alice_message.id)
    assert stored.deleted_at is not None


async def test_other_member_cannot_delete(
    delete_message_use_case: DeleteMessageUseCase, alice_message: tables.MessagesTable, bob: Actor
) -> None:
    with pytest.raises(PermissionDeniedError):
        await delete_message_use_case(actor=bob, message_id=alice_message.id)


async def test_author_without_membership_cannot_delete(
    delete_message_use_case: DeleteMessageUseCase,
    chat_members_repository: ChatMembersRepository,
    alice_message: tables.MessagesTable,
    alice: Actor,
) -> None:
    await _remove_alice_from_chat(chat_members_repository, alice_message, alice)
    with pytest.raises(PermissionDeniedError):
        await delete_message_use_case(actor=alice, message_id=alice_message.id)


async def test_non_member_cannot_delete(
    delete_message_use_case: DeleteMessageUseCase, alice_message: tables.MessagesTable, carol: Actor
) -> None:
    with pytest.raises(PermissionDeniedError):
        await delete_message_use_case(actor=carol, message_id=alice_message.id)


async def test_deleting_an_already_deleted_message_is_idempotent(
    delete_message_use_case: DeleteMessageUseCase,
    messages_repository: MessagesRepository,
    alice_message: tables.MessagesTable,
    alice: Actor,
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
    alice: Actor,
) -> None:
    other, _ = await create_message_use_case(
        actor=alice,
        chat_id=alice_message.chat_id,
        data=schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="still here"),
    )

    await delete_message_use_case(actor=alice, message_id=alice_message.id)
    page = await fetch_messages_use_case(actor=alice, chat_id=alice_message.chat_id)

    assert [message.id for message in page] == [other.id]
