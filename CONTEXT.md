# chat-app

A chat backend: users open direct or group chats, send messages, and track what
they have read. This file is the glossary and nothing else. The decisions taken
live in [`docs/adr/`](docs/adr/); how the system works lives in `app/` and its
tests.

A term is listed only when there is a synonym to reject, or a meaning subtle
enough that code and docs must agree on it. Definitions name columns and
mechanisms where that is what makes them precise.

## Language

**Chat**:
A row in `chats`: a type (`direct` or `group`), an optional title, its creator,
and a pointer to its newest non-deleted message.
_Avoid_: conversation, room, thread

**Direct chat**:
A chat between exactly two users, identified by `direct_key`, the canonical
`min(user_id):max(user_id)` string under a unique constraint. That key is what
makes opening one twice an upsert instead of a read-then-race.
_Avoid_: DM, 1:1

**Actor**:
The authenticated caller of a request: a user id proved by the JWT, carrying no
other user data and not implying the row still exists. Distinct from **Member**,
which is per-chat authorization for that actor.
_Avoid_: principal, current user, authenticated user

**Member**:
The `(chat_id, user_id)` row granting access to a chat, plus that user's read
marker. Necessary for every read or write on a chat; not sufficient for editing
or deleting a message.
_Avoid_: participant, subscriber

**Idempotency key**:
The client-supplied UUID on a send, unique per `(chat_id, idempotency_key)`.
Scoped to one chat, because the key identifies a retry of "send this message to
this chat".
_Avoid_: dedupe key, request id

**Unread**:
A count computed at read time against one marker per member, not a set of
per-message receipt rows.
_Avoid_: unseen, badge count

**Cursor**:
A message id passed as `before_id` or `after_id`. The two are mutually exclusive
on one request.
_Avoid_: page token, offset

**Read marker**:
A member's `last_read_message_id`, the highest id they have acknowledged.
Advances only forward, via `GREATEST` inside the UPDATE.
_Avoid_: read receipt, watermark
