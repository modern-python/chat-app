# Chats

## Shape

`ChatsTable` (`app/database/tables.py`): `chat_type`, optional `title`
(group chats only — `CreateChatUseCase` forces it to `None` for direct chats
even if the request supplied one), `created_by_id`, `last_message_id`
(nullable, repointed by message send/delete — see `messages.md`), and
`direct_key` (nullable, unique). `chat_type` is stored as `sa.Enum(ChatType,
native_enum=False, create_constraint=True, values_callable=...)` — a `VARCHAR`
plus a `CHECK` constraint storing the lowercase string values (`"direct"`,
`"group"`), not a native Postgres enum type. A native enum would need
`alembic-postgresql-enum` for autogenerate to emit correct `ALTER TYPE`
migrations, a dependency not worth buying to store two values. See
`planning/decisions/2026-08-21-sequence-ids-not-snowflakes.md` for the
adjacent id-strategy call.

`ChatMembersTable` is `(chat_id, user_id)` under `uk_chat_members_chat_id_user_id`,
plus `last_read_message_id` and `joined_at`.

## Creating a chat

`POST /api/chats/` → `CreateChatUseCase` (`app/use_cases/create_chat.py`).
`member_ids` from the request is unioned with the actor's own id, so the
creator is always a member even if they omitted themselves.

**Direct** (`chat_type = "direct"`) requires the union to resolve to exactly
two distinct users (`ValidationError` → `400` otherwise), builds
`direct_key = build_direct_key(low, high)`, and checks
`fetch_direct_by_key` first: if a direct chat for this pair already exists,
it's returned as-is with `created=False` (→ `200`). This pre-check does not
close the race — two concurrent requests can both miss it before either
commits. The `INSERT` itself is the real guard: it hits `uq_chats_direct_key`,
and the loser catches `DuplicateKeyError`, rolls back, and re-reads
`fetch_direct_by_key` to return the winner's row. **Group** chats have no
unique constraint on `chats` to collide on, so an unexpected
`DuplicateKeyError` from a group-chat insert is not funnelled into this
recovery path — it re-raises and maps to the standard `409`.

The rollback-then-reread shape (here and in `CreateMessageUseCase`, see
`messages.md`) exists because `Transaction.__aexit__` unconditionally rolls
back and closes the session on an open, uncommitted transaction, which expires
every loaded attribute — returning the just-loaded row from *inside* the
`async with self.transaction:` block without a preceding `commit()` would hand
the caller a detached object.

## Membership and 403-vs-404

Every chat- and message-scoped use case checks membership before doing
anything else (`chat_members_repository.is_member` /
`fetch_member`), and a non-member gets `PermissionDeniedError` → `403` — not
`404`. `FetchChatUseCase` (`app/use_cases/fetch_chat.py`) deliberately returns
`403` for a chat that exists but that the actor isn't in, rather than `404`
pretending it doesn't exist; other use cases follow the same posture for
consistency. One accepted consequence: a non-member can distinguish an
existing message id from a nonexistent one via `404` vs `403` on
`PATCH`/`DELETE /api/messages/{id}/` (see `messages.md` and
`planning/deferred.md`).

## Listing and unread counts

`GET /api/chats/` → `FetchChatsUseCase` (`app/use_cases/fetch_chats.py`), backed
by `ChatsRepository.list_for_user`. Unread count is a correlated scalar
subquery per row, not a Python loop: `count(messages WHERE chat_id = ? AND id
> COALESCE(member.last_read_message_id, 0) AND user_id IS DISTINCT FROM
member.user_id AND deleted_at IS NULL)`, joined against `chat_members` and
ordered by `COALESCE(last_message_id, 0) DESC` so the most recently active
chat sorts first (a chat with no messages yet sorts last, not first). `IS
DISTINCT FROM` rather than `!=` matters because system messages carry
`user_id IS NULL`, and `NULL != me` evaluates to `NULL` in SQL, which would
silently drop every system message from the count.

The use case then loads every listed chat's `last_message` in one bounded
`WHERE id IN (...)` query (`FetchChatsUseCase.__call__`), not one query per
row — the `deleted_at.is_(None)` filter on that query is a self-defending
guard, not the source of truth, since `DeleteMessageUseCase` already repoints
`last_message_id` off a deleted message in the same commit as the delete (see
`messages.md`).

## Marking read

`POST /api/chats/{id}/read/` → `MarkReadUseCase` (`app/use_cases/mark_read.py`).
The requested `last_read_message_id` must name a real message in *this* chat
— `ValidationError` → `400` otherwise, since accepting an arbitrary id would
let a client zero its own unread count by naming a message from another chat
or one that doesn't exist. The marker only ever advances: `ChatMembersRepository.mark_read`
computes `GREATEST(COALESCE(current, 0), requested)` inside the `UPDATE`
itself rather than in Python from a prior read, so two concurrent `POST
/read/` calls can't race a read-modify-write and let the lower id win — the
row lock on the `UPDATE` serializes them.
