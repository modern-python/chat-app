---
summary: The `if connection.in_transaction():` guard in `tests/conftest.py`'s `db_session` teardown silently skips the rollback whenever the outer transaction is already closed.
---

# Per-test rollback is fail-silent on an unexpected commit

## Why it is open

The `if connection.in_transaction():` guard in `tests/conftest.py`'s
`db_session` teardown skips the rollback without error whenever the outer
transaction is already closed. It exists to tolerate tests that legitimately
closed their own transaction, but it can't distinguish that from a session
somewhere having committed the outer transaction instead of nesting a
savepoint under it — that failure mode would leak state into the next test
with no diagnostic.

## Revisit trigger

A test suite flake that looks like cross-test state leakage, or before adding
any code path that opens a session without going through
`database_resources.create_session`.
