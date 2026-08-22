---
summary: The two tests proving the per-test rollback fixture only prove it when run together in file order; run the second alone and it passes vacuously.
---

# Isolation test pair is order-dependent

## Why it is open

`tests/test_main.py::test_db_session_insert_is_visible_within_test` and
`test_db_session_rolls_back_between_tests` together prove the per-test
rollback fixture, but only when pytest runs them in file order: the first
inserts and commits, the second asserts the table is empty. Run the second
alone (e.g. `-k test_db_session_rolls_back_between_tests`) and it passes
vacuously — an empty table before any insert is indistinguishable from a
correctly rolled-back one.

## Revisit trigger

Test order ever becomes non-deterministic (parallel pytest execution,
`pytest-randomly`), or before trusting `-k` output from just this pair as
proof the fixture works.
