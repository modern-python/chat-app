# Glossary

The project's ubiquitous language — the domain terms that code, specs, and
capability pages share. Living prose, no frontmatter, dated by git. Each entry
is a term, what it *is* (not what it does), and the synonyms to avoid.

**Chat**:
A row in `chats`: a `chat_type` (`direct` or `group`), an optional `title`,
the `id` of the user who created it, and a pointer (`last_message_id`) to its
newest non-deleted message. Owns a set of `Member` rows through `chat_members`.
_Avoid_: conversation, room, thread

**Direct chat**:
A `Chat` with `chat_type = "direct"` between exactly two users, identified by
`direct_key` — the canonical `min(user_id):max(user_id)` string under a unique
constraint. Opening a direct chat with the same pair twice returns the same
row; the key is what makes that an upsert instead of a read-then-race. A
`group` chat has no `direct_key` and no member-count ceiling.
_Avoid_: DM, 1:1

**Member**:
A row in `chat_members`: the `(chat_id, user_id)` pair that grants access to a
`Chat`, plus that user's `last_read_message_id`. Membership is what
`is_member`/`fetch_member` check before any read or write on a chat is
authorized; it is necessary but, for editing or deleting a message, not
sufficient — see `Read marker`.
_Avoid_: participant, subscriber

**Idempotency key**:
The client-supplied `idempotency_key` (a UUID) on a send-message request,
unique per `(chat_id, idempotency_key)` — scoped to one chat, not global,
because the key identifies a retry of "send this message to this chat," and
the same key reused in a different chat is a second, independent send. A
repeated key returns the first send's row with `200` instead of creating a
second one with `201`.
_Avoid_: dedupe key, request id

**Unread**:
A message counted by `chats_repository.list_for_user`'s correlated subquery:
`id > member.last_read_message_id` (treating `NULL` as `0`), not authored by
the viewing member (`user_id IS DISTINCT FROM`, so system messages with
`user_id IS NULL` still count), and not soft-deleted. There is no per-message
receipt row — unread is a count computed at read time against one marker per
member, not a set of rows written per message per recipient.
_Avoid_: unseen, badge count

**Cursor**:
A message `id` passed as `before_id` or `after_id` to page `GET
.../messages/`. `before_id` returns older messages, newest-first, excluding
the cursor row; `after_id` returns newer messages, oldest-first, excluding the
cursor row. The two are mutually exclusive on one request. Message ids are a
Postgres identity sequence, so "greater id" is a total order a cursor can walk
without an offset.
_Avoid_: page token, offset

**Read marker**:
A member's `last_read_message_id` — the highest message id that member has
acknowledged reading in that chat. Advanced only forward: `mark_read` sets it
to `GREATEST(current, requested)` inside the UPDATE itself, so an out-of-order
or replayed request naming an earlier message can never move it backwards and
resurrect messages that were already read.
_Avoid_: read receipt, watermark
