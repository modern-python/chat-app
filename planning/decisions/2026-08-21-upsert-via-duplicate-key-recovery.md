---
summary: Direct-chat creation and message send recover from a unique-constraint violation and re-read, rather than trusting a pre-check.
---

# Upsert by recovering from DuplicateKeyError

Both `CreateChatUseCase` and `CreateMessageUseCase` read first to see whether
the row already exists, then insert. The read is an optimisation. The
correctness guarantee is the `except DuplicateKeyError:` branch, which rolls
back and re-reads the row the winner committed.

Both recovery paths are exercised by tests, through repository subclasses
(`_RacingChatsRepository`, `_RacingMessagesRepository`) whose `create` raises
`DuplicateKeyError` and whose lookup misses once before delegating to the real
implementation. That simulates a database condition at a seam the tests already
own, rather than mocking the unit under test.

## Rejected: the pre-check alone

The original design assumed a read inside the transaction made the insert safe.
It does not. At READ COMMITTED two concurrent "open a DM with Bob" requests both
miss the read, both insert, and the loser violates `uq_chats_direct_key`. That
surfaces as a `409` to a user who should simply have received the existing chat,
which contradicts the reason `direct_key` exists at all.

`@postgres_retry` does not rescue it either: `db-retry` retries serialization
and connection failures, not integrity violations.

## Rejected: `SELECT ... FOR UPDATE`

There is no row to lock. The race is between two inserts of a row that does not
yet exist, so row-level locking has nothing to take.

## Consequence

The happy path costs one extra read. The contended path costs a rolled-back
insert plus a re-read, which is strictly better than returning an error for a
request that should have succeeded.

## Revisit trigger

A write path where the losing racer's rollback is too expensive to accept, or a
move to an `INSERT ... ON CONFLICT` form that still needs the same re-read.
