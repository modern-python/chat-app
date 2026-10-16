# A message send is one INSERT ... ON CONFLICT DO UPDATE

`MessagesRepository.get_or_create` writes a send as one `INSERT ... ON CONFLICT
ON CONSTRAINT uk_messages_chat_id_idempotency_key DO UPDATE SET idempotency_key
= EXCLUDED.idempotency_key RETURNING ..., xmax = 0`. The no-op update makes a
replay return the existing row from the same statement, and a request racing an
uncommitted insert of the same key waits on that row's lock, then gets the
winner's row. `xmax = 0` is true only for a row version the statement inserted,
so the use case can answer 201 or 200 and skip the `last_message_id` update on a
replay. The read-then-insert with `DuplicateKeyError` recovery from
[0005](0005-upsert-via-duplicate-key-recovery.md) cost two round trips per new
message and re-read the winner outside the retried transaction. `ON CONFLICT DO
NOTHING` returns no row to the loser, and advanced-alchemy's `upsert` reads
first. The cost: every replay writes a row version and consumes a sequence
value, so a retried send leaves a gap in message ids that
[0001](0001-sequence-ids-not-snowflakes.md)'s client gap detection answers with
one empty catch-up fetch. Postgres does not document `xmax` in `RETURNING`; the
replay and concurrent tests in `tests/use_cases/test_create_message.py` would
catch a change.
