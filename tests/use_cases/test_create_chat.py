import pytest

from app.database import tables
from app.exceptions import PermissionDeniedError
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase


async def test_direct_chat_is_created_with_both_members(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> None:
    chat = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    assert chat.chat_type is tables.ChatType.DIRECT
    assert chat.direct_key == tables.build_direct_key(alice.id, bob.id)
    assert {member.user_id for member in chat.members} == {alice.id, bob.id}


async def test_direct_chat_is_idempotent_for_the_same_pair(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> None:
    first = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    second = await create_chat_use_case(
        bob, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[alice.id])
    )
    assert first.id == second.id
    # `second` is returned from the early-return, no-write path (existing direct chat found).
    # Its relationship must still be readable without triggering a lazy load on a closed/rolled-back session.
    assert {member.user_id for member in second.members} == {alice.id, bob.id}


async def test_direct_chat_rejects_more_than_two_members(
    create_chat_use_case: CreateChatUseCase,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    carol: tables.UsersTable,
) -> None:
    with pytest.raises(PermissionDeniedError):
        await create_chat_use_case(
            alice,
            schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id, carol.id]),
        )


async def test_group_chat_includes_the_creator(
    create_chat_use_case: CreateChatUseCase,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    carol: tables.UsersTable,
) -> None:
    chat = await create_chat_use_case(
        alice,
        schemas.CreateChatRequest(chat_type=tables.ChatType.GROUP, member_ids=[bob.id, carol.id], title="Team"),
    )
    assert chat.direct_key is None
    assert {member.user_id for member in chat.members} == {alice.id, bob.id, carol.id}
