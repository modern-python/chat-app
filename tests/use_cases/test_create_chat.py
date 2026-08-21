import pytest
from advanced_alchemy.exceptions import DuplicateKeyError

from app.database import tables
from app.exceptions import ValidationError
from app.repositories.chats_repository import ChatsRepository
from app.schemas import api as schemas
from app.use_cases.create_chat import CreateChatUseCase


class _RacingChatsRepository(ChatsRepository):
    """Simulates losing a create-direct-chat race.

    The pre-check misses (as if the winner's row weren't committed/visible yet), the insert
    then collides with the winner's now-committed row (DuplicateKeyError), and the recovery
    re-read must find it.
    """

    _missed_precheck: bool = False

    async def fetch_direct_by_key(self, direct_key: str) -> tables.ChatsTable | None:
        if not self._missed_precheck:
            self._missed_precheck = True
            return None
        return await super().fetch_direct_by_key(direct_key)

    async def create(self, *_args: object, **_kwargs: object) -> tables.ChatsTable:
        msg = "simulated race: another request already created this direct chat"
        raise DuplicateKeyError(msg)


class _AlwaysDuplicateChatsRepository(ChatsRepository):
    """Stub whose create() always raises DuplicateKeyError.

    Simulates an unexpected unique-constraint violation at the seam the real repository
    would raise it from.
    """

    async def create(self, *_args: object, **_kwargs: object) -> tables.ChatsTable:
        msg = "simulated duplicate key"
        raise DuplicateKeyError(msg)


async def test_direct_chat_is_created_with_both_members(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> None:
    chat, created = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    assert created is True
    assert chat.chat_type is tables.ChatType.DIRECT
    assert chat.direct_key == tables.build_direct_key(alice.id, bob.id)
    assert {member.user_id for member in chat.members} == {alice.id, bob.id}


async def test_direct_chat_is_idempotent_for_the_same_pair(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> None:
    first, first_created = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    second, second_created = await create_chat_use_case(
        bob, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[alice.id])
    )
    assert first.id == second.id
    assert first_created is True
    assert second_created is False
    # `second` is returned from the early-return, no-write path (existing direct chat found).
    # Its relationship must still be readable without triggering a lazy load on a closed/rolled-back session.
    assert {member.user_id for member in second.members} == {alice.id, bob.id}


async def test_direct_chat_creation_recovers_from_a_concurrent_duplicate_key(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> None:
    # A real winner: create the direct chat normally first, so a genuinely committed row exists.
    winner, winner_created = await create_chat_use_case(
        alice, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[bob.id])
    )
    assert winner_created is True
    # Captured now, not read off `winner` after the racer runs: the racer shares this session,
    # and its own recovery `rollback()` expires every object already loaded on that session -
    # including `winner` - exactly the hazard the surrounding comments describe, just now
    # crossing between two calls that happen to share a session instead of within one call.
    winner_id = winner.id

    # The losing side of the race, sharing `create_chat_use_case`'s own transaction/session so
    # the winner row (committed above) is visible to the recovery re-read.
    racer = CreateChatUseCase(
        transaction=create_chat_use_case.transaction,
        chats_repository=_RacingChatsRepository(
            session=create_chat_use_case.chats_repository.repository.session, auto_commit=False
        ),
        chat_members_repository=create_chat_use_case.chat_members_repository,
    )
    loser, loser_created = await racer(
        bob, schemas.CreateChatRequest(chat_type=tables.ChatType.DIRECT, member_ids=[alice.id])
    )
    assert loser_created is False
    assert loser.id == winner_id


async def test_group_chat_reraises_an_unexpected_duplicate_key(
    create_chat_use_case: CreateChatUseCase, alice: tables.UsersTable, bob: tables.UsersTable
) -> None:
    # Group chats have no unique constraint to race on `chats`; a DuplicateKeyError there is
    # unexpected and must propagate (mapping to the standard 409), not be funnelled into the
    # direct-chat recovery path.
    broken = CreateChatUseCase(
        transaction=create_chat_use_case.transaction,
        chats_repository=_AlwaysDuplicateChatsRepository(
            session=create_chat_use_case.chats_repository.repository.session, auto_commit=False
        ),
        chat_members_repository=create_chat_use_case.chat_members_repository,
    )
    with pytest.raises(DuplicateKeyError):
        await broken(alice, schemas.CreateChatRequest(chat_type=tables.ChatType.GROUP, member_ids=[bob.id]))


async def test_direct_chat_rejects_more_than_two_members(
    create_chat_use_case: CreateChatUseCase,
    alice: tables.UsersTable,
    bob: tables.UsersTable,
    carol: tables.UsersTable,
) -> None:
    with pytest.raises(ValidationError):
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
    chat, created = await create_chat_use_case(
        alice,
        schemas.CreateChatRequest(chat_type=tables.ChatType.GROUP, member_ids=[bob.id, carol.id], title="Team"),
    )
    assert created is True
    assert chat.direct_key is None
    assert {member.user_id for member in chat.members} == {alice.id, bob.id, carol.id}
