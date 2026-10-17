import asyncio
import re
import typing
import uuid

import pytest
import sqlalchemy as sa
from db_retry import Transaction
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import security
from app.actor import Actor
from app.database import tables
from app.database.resources import create_database_engine, create_session
from app.exceptions import PermissionDeniedError
from app.repositories.chat_members_repository import ChatMembersRepository
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.create_message import CreateMessageUseCase
from tests.api.helpers import count_statements
from tests.factories import UserFactory


async def test_send_returns_created_true_on_first_call(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: Actor
) -> None:
    message, created = await create_message_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi")
    )
    assert created is True
    assert message.text == "hi"


async def test_repeated_idempotency_key_returns_the_same_message(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: Actor
) -> None:
    key = uuid.uuid4()
    first, first_created = await create_message_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )
    second, second_created = await create_message_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.SendMessageRequest(idempotency_key=key, text="hi again")
    )
    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert second.text == "hi"


async def test_send_updates_chat_last_message_id(
    create_message_use_case: CreateMessageUseCase,
    chats_repository: ChatsRepository,
    direct_chat: tables.ChatsTable,
    alice: Actor,
) -> None:
    message, _ = await create_message_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi")
    )
    chat = await chats_repository.get_one(id=direct_chat.id)
    assert chat.last_message_id == message.id


async def test_non_member_cannot_send(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, carol: Actor
) -> None:
    with pytest.raises(PermissionDeniedError):
        await create_message_use_case(
            actor=carol,
            chat_id=direct_chat.id,
            data=schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi"),
        )


async def test_same_idempotency_key_in_two_different_chats_creates_two_messages(
    create_message_use_case: CreateMessageUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: Actor,
    carol: Actor,
) -> None:
    other_chat, _ = await create_chat_use_case(
        actor=alice, data=schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    key = uuid.uuid4()

    first, first_created = await create_message_use_case(
        actor=alice, chat_id=direct_chat.id, data=schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )
    second, second_created = await create_message_use_case(
        actor=alice, chat_id=other_chat.id, data=schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )

    assert first_created is True
    assert second_created is True
    assert first.id != second.id
    assert first.chat_id == direct_chat.id
    assert second.chat_id == other_chat.id


async def test_send_writes_the_message_with_a_single_statement(
    create_message_use_case: CreateMessageUseCase,
    direct_chat: tables.ChatsTable,
    alice: Actor,
    db_session: AsyncSession,
) -> None:
    with count_statements(db_session) as statements:
        await create_message_use_case(
            actor=alice,
            chat_id=direct_chat.id,
            data=schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi"),
        )

    message_statements: typing.Final = [statement for statement in statements if re.search(r"\bmessages\b", statement)]
    assert len(message_statements) == 1, message_statements
    assert "ON CONFLICT" in message_statements[0]


async def _wait_until_blocked_on_a_lock(engine: AsyncEngine, pid: int) -> None:
    wait_event_type = None
    while wait_event_type != "Lock":
        await asyncio.sleep(0.01)
        async with engine.connect() as connection:
            wait_event_type = await connection.scalar(
                sa.text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
            )


async def test_send_returns_the_message_a_concurrent_request_created_with_the_same_key() -> None:
    """INVARIANT: a send racing an uncommitted insert of the same key waits for it and returns that row.

    It reports created=False and leaves last_message_id alone. Broken by switching to ON CONFLICT
    DO NOTHING, whose RETURNING yields no row for the request that loses the race.
    """
    engine: typing.Final = create_database_engine()
    idempotency_key: typing.Final = uuid.uuid4()
    setup_session: typing.Final = create_session(engine)
    user: typing.Final = UserFactory.build(
        username=f"racer-{idempotency_key}",
        password_hash=security.hash_password("hunter2hunter2"),
        display_name="Racer",
    )
    setup_session.add(user)
    await setup_session.flush()
    chat: typing.Final = tables.ChatsTable(chat_type=tables.ChatType.GROUP, title="race", created_by_id=user.id)
    setup_session.add(chat)
    await setup_session.flush()
    setup_session.add(tables.ChatMembersTable(chat_id=chat.id, user_id=user.id))
    await setup_session.commit()
    await setup_session.close()
    try:
        async with engine.connect() as concurrent_request:
            await concurrent_request.execute(
                sa.insert(tables.MessagesTable).values(
                    chat_id=chat.id, user_id=user.id, idempotency_key=idempotency_key, text="first"
                )
            )
            session: typing.Final = create_session(engine)
            pid: typing.Final = await (await session.connection()).scalar(sa.text("SELECT pg_backend_pid()"))
            use_case: typing.Final = CreateMessageUseCase(
                transaction=Transaction(session=session),
                chats_repository=ChatsRepository(session=session, auto_commit=False),
                chat_members_repository=ChatMembersRepository(session=session, auto_commit=False),
                messages_repository=MessagesRepository(session=session, auto_commit=False),
            )
            pending: typing.Final = asyncio.create_task(
                use_case(
                    actor=Actor(id=user.id),
                    chat_id=chat.id,
                    data=schemas.SendMessageRequest(idempotency_key=idempotency_key, text="second"),
                )
            )
            await asyncio.wait_for(_wait_until_blocked_on_a_lock(engine, pid), timeout=5)
            await concurrent_request.commit()
            message, created = await pending
            await session.close()
        async with engine.connect() as connection:
            last_message_id: typing.Final = await connection.scalar(
                sa.select(tables.ChatsTable.last_message_id).where(tables.ChatsTable.id == chat.id)
            )
        assert message.text == "first"
        assert created is False
        assert last_message_id is None
    finally:
        async with engine.begin() as connection:
            await connection.execute(sa.delete(tables.MessagesTable).where(tables.MessagesTable.chat_id == chat.id))
            await connection.execute(
                sa.delete(tables.ChatMembersTable).where(tables.ChatMembersTable.chat_id == chat.id)
            )
            await connection.execute(sa.delete(tables.ChatsTable).where(tables.ChatsTable.id == chat.id))
            await connection.execute(sa.delete(tables.UsersTable).where(tables.UsersTable.id == user.id))
        await engine.dispose()
