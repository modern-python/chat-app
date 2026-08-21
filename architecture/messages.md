# Messages

## Shape

`MessagesTable` (`app/database/tables.py`): `chat_id`, nullable `user_id`
(`NULL` for system messages, e.g. "Bob joined" — no sentinel user), an
`idempotency_key` (UUID), `text`, `created_at`, nullable `edited_at` /
`deleted_at`. `ix_messages_chat_id_id` is a composite index on `(chat_id, id)`
— there is no standalone index on `chat_id` alone, because every query that
would use one (membership-scoped listing, cursor pagination) is already served
by the composite. `uk_messages_chat_id_idempotency_key` is a unique constraint
on `(chat_id, idempotency_key)`, **not** a global unique constraint on the key
alone — see `Idempotency key` in `glossary.md`.

## Sending: idempotent with a concurrent-retry fallback

`POST /api/chats/{id}/messages/` → `CreateMessageUseCase`
(`app/use_cases/create_message.py`). After the membership check, it pre-reads
`fetch_by_idempotency_key(chat_id, key)`; a hit returns that row with
`created=False` (→ `200`) without writing anything. A miss proceeds to
`INSERT`, then updates `chats.last_message_id` to the new message's id in the
same commit, and returns `created=True` (→ `201`).

The pre-check does not close the race between two concurrent sends of the
same key: both can miss it before either commits. The unique constraint is
the real guard — the loser's `INSERT` raises `DuplicateKeyError`, which is
caught, the transaction is rolled back (`await self.transaction.rollback()`,
not a `return` from inside the `async with` block — see the same
`__aexit__`-detaches-loaded-attributes hazard documented in `chats.md`), and
the loser re-reads `fetch_by_idempotency_key` outside the block to return the
winner's row with `created=False`. If that re-read still finds nothing, it's
treated as impossible (`RuntimeError`, `# pragma: no cover`) — the unique
constraint that just fired guarantees a matching row exists.

Reusing the same key in a different chat is a second, independent send:
idempotency is scoped `(chat_id, key)` because the key identifies a retry of
"send to this chat," not a retry across the table.

## Pagination

`GET /api/chats/{id}/messages/` → `FetchMessagesUseCase`
(`app/use_cases/fetch_messages.py`) → `MessagesRepository.list_page`.
`before_id` and `after_id` are mutually exclusive (`ValidationError` → `400`
if both are set). `before_id` returns strictly older messages, newest-first,
excluding the cursor row itself; `after_id` returns strictly newer messages,
oldest-first, excluding the cursor row — the ascending form exists for
resync-on-reconnect in the realtime follow-on and is why the composite index
is shaped the way it is. `limit` is clamped to `MAX_PAGE_SIZE = 100` (silently
capped, not rejected) but rejected outright below `1` (`ValidationError` →
`400`). All variants filter `deleted_at IS NULL` — a soft-deleted message
disappears from every listing on its next fetch rather than appearing as a
tombstone.

## Edit and delete: author **and** member

`PATCH /api/messages/{id}/` and `DELETE /api/messages/{id}/` are gated by
`fetch_message_for_author` (`app/use_cases/message_authorization.py`), shared
by `EditMessageUseCase` and `DeleteMessageUseCase` so the check order is
defined in exactly one place: existence (`get_one` → `NotFoundError` → `404`),
then chat membership (→ `403`), then authorship — `message.user_id !=
actor.id` (→ `403`). Authorship alone is not sufficient: an author who has
been removed from the chat (membership deleted) can no longer edit or delete
their own message, because the membership check runs first and unconditionally
— this is the one state where authorship and membership disagree, and the
only state that proves the membership check does something the authorship
check doesn't already cover on its own.

One accepted consequence of checking membership before authorship: a
non-member gets `403` for both an existing message and (via the `404` from
`get_one`) a nonexistent one, so the two are distinguishable by status code.
This mirrors the same `FetchChatUseCase` 403-vs-404 posture in `chats.md`, and
is recorded, not treated as a bug, in `planning/deferred.md`.

`EditMessageUseCase` additionally rejects editing an already-deleted message
with `ConflictError` → `409` (the actor is authorized; the request conflicts
with the message's current state). `DeleteMessageUseCase` treats a second
delete of an already-deleted message as a no-op returning `204` — DELETE is
idempotent under HTTP semantics where PATCH is not.

Deleting a chat's newest message repoints `chats.last_message_id` atomically,
in the same commit as the soft delete: `DeleteMessageUseCase` checks whether
`chat.last_message_id == message_id`, and if so looks up
`fetch_latest_active` (the next-newest non-deleted message, or `None` if none
remains) and writes that back. Without this, the chat listing's preview and
its activity ordering (`chats.md`) would both keep reading a deleted message
until something else happened to send a new one.

## Error vocabulary

Registered in `build_app` (`app/api/app.py`) via `app/api/exception_handlers.py`,
mapping `app/exceptions.py`'s domain hierarchy plus a few `advanced_alchemy`
exceptions:

| Exception | Status | Meaning |
|---|---|---|
| `advanced_alchemy.exceptions.NotFoundError` | 404 | the resource doesn't exist |
| `app.exceptions.PermissionDeniedError` | 403 | authenticated, but not authorized for this action |
| `app.exceptions.ValidationError` | 400 | well-formed request, violates a domain invariant |
| `app.exceptions.ConflictError` | 409 | authorized, but conflicts with the resource's current state |
| `advanced_alchemy.exceptions.DuplicateKeyError` | 409 | unique-constraint violation not otherwise recovered |
| `advanced_alchemy.exceptions.ForeignKeyError` | 400 | a referenced id doesn't exist |

Litestar's own `NotAuthorizedException` (401) is used exactly once, for a
failed login (`app/api/endpoints/auth.py::login`) — see `auth.md`. It is the
one place `app.exceptions` is deliberately not used, because a bad
credential is an identification failure, not a downstream authorization
decision on an already-identified actor.
