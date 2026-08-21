import uuid

import pytest
from advanced_alchemy.exceptions import DuplicateKeyError

from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas import api as schemas
from app.use_cases.create_message import CreateMessageUseCase


class _RacingMessagesRepository(MessagesRepository):
    """Simulate losing a concurrent-send-with-the-same-key race.

    The pre-check misses (as if the winner's row weren't committed/visible yet), the insert
    then collides with the winner's now-committed row (DuplicateKeyError), and the recovery
    re-read must find it.
    """

    _missed_precheck: bool = False

    async def fetch_by_idempotency_key(self, idempotency_key: uuid.UUID) -> tables.MessagesTable | None:
        if not self._missed_precheck:
            self._missed_precheck = True
            return None
        return await super().fetch_by_idempotency_key(idempotency_key)

    async def create(self, *_args: object, **_kwargs: object) -> tables.MessagesTable:
        msg = "simulated race: another request already sent this message"
        raise DuplicateKeyError(msg)


async def test_send_returns_created_true_on_first_call(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    message, created = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi")
    )
    assert created is True
    assert message.text == "hi"


async def test_repeated_idempotency_key_returns_the_same_message(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    key = uuid.uuid4()
    first, first_created = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )
    second, second_created = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=key, text="hi again")
    )
    assert first_created is True
    assert second_created is False
    assert first.id == second.id
    assert second.text == "hi"


async def test_send_updates_chat_last_message_id(
    create_message_use_case: CreateMessageUseCase,
    chats_repository: ChatsRepository,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
) -> None:
    message, _ = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi")
    )
    chat = await chats_repository.get_one(id=direct_chat.id)
    assert chat.last_message_id == message.id


async def test_non_member_cannot_send(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, carol: tables.UsersTable
) -> None:
    with pytest.raises(PermissionDeniedError):
        await create_message_use_case(
            carol, direct_chat.id, schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi")
        )


async def test_concurrent_duplicate_key_recovers_the_winners_message(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    key = uuid.uuid4()
    winner, winner_created = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )
    assert winner_created is True
    winner_id = winner.id

    # Shares the winner's session/transaction so the committed row is visible to the recovery
    # re-read, same setup as CreateChatUseCase's equivalent race test.
    racer = CreateMessageUseCase(
        transaction=create_message_use_case.transaction,
        chats_repository=create_message_use_case.chats_repository,
        chat_members_repository=create_message_use_case.chat_members_repository,
        messages_repository=_RacingMessagesRepository(
            session=create_message_use_case.messages_repository.repository.session, auto_commit=False
        ),
    )
    loser, loser_created = await racer(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=key, text="hi again")
    )
    assert loser_created is False
    assert loser.id == winner_id
