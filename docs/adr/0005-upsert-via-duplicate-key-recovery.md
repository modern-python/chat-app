# Upsert by recovering from DuplicateKeyError

`CreateChatUseCase` reads first to see whether the direct chat already exists
and then inserts, but the read is only an optimisation:
the correctness guarantee is the `except DuplicateKeyError` branch, which rolls
back and re-reads the row the winner committed. The pre-check alone does not
make the insert safe. At READ COMMITTED two concurrent "open a DM with Bob"
requests both miss the read, both insert, and the loser violates
`uq_chats_direct_key`, which surfaces as a `409` to a user who should simply
have received the existing chat. `@postgres_retry` does not rescue it either,
because `db-retry` retries serialization and connection failures, not integrity
violations, and `SELECT ... FOR UPDATE` has nothing to take, since the race is
between two inserts of a row that does not yet exist. The recovery path is
exercised by a repository subclass, `_RacingChatsRepository`, whose `create`
raises and whose lookup misses once, simulating the database condition at a seam
the tests already own. Message sends used this pattern too until
[0012](0012-message-send-is-one-upsert.md) replaced it with a single statement.
