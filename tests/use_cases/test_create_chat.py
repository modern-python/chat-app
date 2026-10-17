import asyncio
import typing

import pytest
import sqlalchemy as sa
from db_retry import Transaction
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import security
from app.actor import Actor
from app.database import tables
from app.database.resources import create_database_engine, create_session
from app.exceptions import ValidationError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from tests.api.helpers import count_statements
from tests.factories import UserFactory


async def test_direct_chat_is_created_with_both_members(
    create_chat_use_case: CreateChatUseCase, alice: Actor, bob: Actor
) -> None:
    chat, created = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    assert created is True
    assert chat.chat_type is tables.ChatType.DIRECT
    assert chat.direct_key == tables.build_direct_key(alice.id, bob.id)
    assert {member.user_id for member in chat.members} == {alice.id, bob.id}


async def test_direct_chat_is_idempotent_for_the_same_pair(
    create_chat_use_case: CreateChatUseCase, alice: Actor, bob: Actor
) -> None:
    first, first_created = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    second, second_created = await create_chat_use_case(
        actor=bob, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[alice.id])
    )
    assert first.id == second.id
    assert first_created is True
    assert second_created is False
    assert {member.user_id for member in second.members} == {alice.id, bob.id}


async def test_direct_chat_rejects_more_than_two_members(
    create_chat_use_case: CreateChatUseCase,
    alice: Actor,
    bob: Actor,
    carol: Actor,
) -> None:
    with pytest.raises(ValidationError):
        await create_chat_use_case(
            actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id, carol.id])
        )


async def test_group_chat_includes_the_creator(
    create_chat_use_case: CreateChatUseCase,
    alice: Actor,
    bob: Actor,
    carol: Actor,
) -> None:
    chat, created = await create_chat_use_case(
        actor=alice,
        data=schemas.CreateChatRequest(chat_type=tables.ChatType.GROUP, member_ids=[bob.id, carol.id], title="Team"),
    )
    assert created is True
    assert chat.direct_key is None
    assert {member.user_id for member in chat.members} == {alice.id, bob.id, carol.id}


def _round_trips(statements: list[str]) -> list[str]:
    return [statement for statement in statements if not statement.startswith(("SAVEPOINT", "RELEASE SAVEPOINT"))]


async def test_direct_chat_creation_takes_two_statements(
    create_chat_use_case: CreateChatUseCase, alice: Actor, bob: Actor, db_session: AsyncSession
) -> None:
    with count_statements(db_session) as statements:
        await create_chat_use_case(
            actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
        )

    round_trips: typing.Final = _round_trips(statements)
    assert len(round_trips) == 2, round_trips
    assert "ON CONFLICT" in round_trips[0]


async def test_direct_chat_replay_takes_two_statements(
    create_chat_use_case: CreateChatUseCase, alice: Actor, bob: Actor, db_session: AsyncSession
) -> None:
    await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    with count_statements(db_session) as statements:
        await create_chat_use_case(
            actor=bob, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[alice.id])
        )

    round_trips: typing.Final = _round_trips(statements)
    assert len(round_trips) == 2, round_trips
    assert "ON CONFLICT" in round_trips[0]


async def _wait_until_blocked_on_a_lock(engine: AsyncEngine, pid: int) -> None:
    wait_event_type = None
    while wait_event_type != "Lock":
        await asyncio.sleep(0.01)
        async with engine.connect() as connection:
            wait_event_type = await connection.scalar(
                sa.text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
            )


async def test_direct_chat_returns_the_chat_a_concurrent_request_created_for_the_same_pair() -> None:
    """INVARIANT: a direct-chat create racing an uncommitted insert of the same pair waits and returns that chat.

    It reports created=False and inserts no members of its own. Broken by switching to ON CONFLICT
    DO NOTHING, whose RETURNING yields no row for the request that loses the race.
    """
    engine: typing.Final = create_database_engine()
    setup_session: typing.Final = create_session(engine)
    users: typing.Final = [
        UserFactory.build(
            username=f"racer-{index}-{id(setup_session)}",
            password_hash=security.hash_password("hunter2hunter2"),
            display_name="Racer",
        )
        for index in range(2)
    ]
    setup_session.add_all(users)
    await setup_session.commit()
    await setup_session.close()
    first, second = (user.id for user in users)
    direct_key: typing.Final = tables.build_direct_key(first, second)
    try:
        async with engine.connect() as concurrent_request:
            chat_id: typing.Final = await concurrent_request.scalar(
                sa.insert(tables.ChatsTable)
                .values(chat_type=tables.ChatType.DIRECT, created_by_id=first, direct_key=direct_key)
                .returning(tables.ChatsTable.id)
            )
            await concurrent_request.execute(
                sa.insert(tables.ChatMembersTable),
                [{"chat_id": chat_id, "user_id": first}, {"chat_id": chat_id, "user_id": second}],
            )
            session: typing.Final = create_session(engine)
            pid: typing.Final = await (await session.connection()).scalar(sa.text("SELECT pg_backend_pid()"))
            use_case: typing.Final = CreateChatUseCase(
                transaction=Transaction(session=session),
                chats_repository=ChatsRepository(session=session, auto_commit=False),
                chat_members_repository=ChatMembersRepository(session=session, auto_commit=False),
            )
            pending: typing.Final = asyncio.create_task(
                use_case(
                    actor=Actor(id=second),
                    data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[first]),
                )
            )
            await asyncio.wait_for(_wait_until_blocked_on_a_lock(engine, pid), timeout=5)
            await concurrent_request.commit()
            chat, created = await pending
            await session.close()
        assert chat.id == chat_id
        assert created is False
        assert sorted(member.user_id for member in chat.members) == sorted([first, second])
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                sa.delete(tables.ChatMembersTable).where(tables.ChatMembersTable.user_id.in_([first, second]))
            )
            await connection.execute(sa.delete(tables.ChatsTable).where(tables.ChatsTable.direct_key == direct_key))
            await connection.execute(sa.delete(tables.UsersTable).where(tables.UsersTable.id.in_([first, second])))
        await engine.dispose()
