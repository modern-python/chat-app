import uuid

import pytest
from advanced_alchemy.exceptions import DuplicateKeyError

from app.database import tables
from app.exceptions import PermissionDeniedError
from app.repositories.chats_repository import ChatsRepository
from app.repositories.messages_repository import MessagesRepository
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase
from app.use_cases.create_message import CreateMessageUseCase


class _RacingMessagesRepository(MessagesRepository):
    """Simulate losing a concurrent-send-with-the-same-key race.

    The pre-check misses (as if the winner's row weren't committed/visible yet), the insert
    then collides with the winner's now-committed row (DuplicateKeyError), and the recovery
    re-read must find it.
    """

    _missed_precheck: bool = False

    async def fetch_by_idempotency_key(self, chat_id: int, idempotency_key: uuid.UUID) -> tables.MessagesTable | None:
        if not self._missed_precheck:
            self._missed_precheck = True
            return None
        return await super().fetch_by_idempotency_key(chat_id, idempotency_key)

    async def create(self, *_args: object, **_kwargs: object) -> tables.MessagesTable:
        msg = "simulated race: another request already sent this message"
        raise DuplicateKeyError(msg)


class _NeverFoundMessagesRepository(MessagesRepository):
    """Simulates a race whose recovery re-read can never find the winner's row.

    Both `fetch_by_idempotency_key` calls (the pre-check and the post-rollback recovery
    re-read) return `None`, and `create()` always raises `DuplicateKeyError` - a state the
    unique constraint on `(chat_id, idempotency_key)` should make unreachable in production,
    exercised here only to prove `CreateMessageUseCase` raises `RuntimeError` rather than
    returning `None` silently.
    """

    async def fetch_by_idempotency_key(
        self,
        chat_id: int,  # noqa: ARG002
        idempotency_key: uuid.UUID,  # noqa: ARG002
    ) -> tables.MessagesTable | None:
        return None

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
    assert loser.text == "hi"


async def test_send_recovery_raises_if_the_winners_row_is_unreadable(
    create_message_use_case: CreateMessageUseCase, direct_chat: tables.ChatsTable, alice: tables.UsersTable
) -> None:
    broken = CreateMessageUseCase(
        transaction=create_message_use_case.transaction,
        chats_repository=create_message_use_case.chats_repository,
        chat_members_repository=create_message_use_case.chat_members_repository,
        messages_repository=_NeverFoundMessagesRepository(
            session=create_message_use_case.messages_repository.repository.session, auto_commit=False
        ),
    )
    with pytest.raises(RuntimeError, match="could not be found"):
        await broken(alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=uuid.uuid4(), text="hi"))


async def test_same_idempotency_key_in_two_different_chats_creates_two_messages(
    create_message_use_case: CreateMessageUseCase,
    create_chat_use_case: CreateChatUseCase,
    direct_chat: tables.ChatsTable,
    alice: tables.UsersTable,
    carol: tables.UsersTable,
) -> None:
    # Idempotency is scoped per (chat_id, idempotency_key): the key identifies a retry of
    # "send to this chat", not a retry across the whole table, so reusing it in a different
    # chat is a second, independent send.
    other_chat, _ = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[carol.id])
    )
    key = uuid.uuid4()

    first, first_created = await create_message_use_case(
        alice, direct_chat.id, schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )
    second, second_created = await create_message_use_case(
        alice, other_chat.id, schemas.SendMessageRequest(idempotency_key=key, text="hi")
    )

    assert first_created is True
    assert second_created is True
    assert first.id != second.id
    assert first.chat_id == direct_chat.id
    assert second.chat_id == other_chat.id
