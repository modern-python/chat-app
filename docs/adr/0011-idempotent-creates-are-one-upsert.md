# Idempotent creates are one INSERT ... ON CONFLICT DO UPDATE

Message sends (`MessagesRepository.get_or_create`, conflicting on
`uk_messages_chat_id_idempotency_key`) and direct chats
(`ChatsRepository.get_or_create_direct`, conflicting on `direct_key`) are each
written by one `INSERT ... ON CONFLICT ... DO UPDATE SET <key> = EXCLUDED.<key>
RETURNING ..., xmax = 0`. The no-op update returns the existing row on a replay,
and a request racing an uncommitted insert of the same key waits on its lock and
then gets the winner's row. `xmax = 0` is true only for a row version the
statement inserted, so it decides 201 or 200 and whether the follow-up writes
run. A read before the insert cannot make it safe: at READ COMMITTED both
requests miss the read, `postgres_retry` does not retry the loser's integrity
error, and `SELECT ... FOR UPDATE` has no row to lock yet. Re-reading after a
`DuplicateKeyError` worked but cost a round trip and ran outside the retried
transaction; `ON CONFLICT DO NOTHING` returns no row to the loser. A replay
writes a row version and consumes a sequence value, so a retried send leaves a
gap that [ADR-0001](0001-sequence-ids-not-snowflakes.md)'s gap detection answers
with one empty fetch, and a DM replay takes three statements where a pre-check
took two. Postgres does not document `xmax` in `RETURNING`; the concurrent
tests in `test_create_message.py` and `test_create_chat.py` would catch a change.
