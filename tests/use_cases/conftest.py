import typing
import uuid

import modern_di
import pytest
from modern_di_pytest import expose
from sqlalchemy.ext.asyncio import AsyncSession

from app import ioc, security
from app.database import tables
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.create_message import CreateMessageUseCase
from tests.factories import UserFactory


@pytest.fixture
async def request_container(
    di_container: modern_di.Container,
    db_session: AsyncSession,  # noqa: ARG001 - forces db_session's engine override to run first
) -> typing.AsyncIterator[modern_di.Container]:
    async with di_container.build_child_container(scope=modern_di.Scope.REQUEST) as container:
        yield container


# One pytest fixture per provider on both groups, named after the class attribute.
# Every use case and repository added in later tasks becomes a fixture automatically,
# so no test file has to hand-assemble dependencies.
expose(ioc.Repositories, ioc.UseCases, container_fixture="request_container")


async def _make_user(session: AsyncSession, username: str) -> tables.UsersTable:
    user: typing.Final = UserFactory.build(
        username=username,
        password_hash=security.hash_password("hunter2hunter2"),
        display_name=username.title(),
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def alice(db_session: AsyncSession) -> tables.UsersTable:
    return await _make_user(db_session, "alice")


@pytest.fixture
async def bob(db_session: AsyncSession) -> tables.UsersTable:
    return await _make_user(db_session, "bob")


@pytest.fixture
async def carol(db_session: AsyncSession) -> tables.UsersTable:
    return await _make_user(db_session, "carol")


@pytest.fixture
async def direct_chat(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> tables.ChatsTable:
    chat, _ = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    return chat


@pytest.fixture
async def alice_message(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> tables.MessagesTable:
    message, _ = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hello")
    )
    return message
