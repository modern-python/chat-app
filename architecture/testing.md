# Testing

`just test` cycles the DB (`alembic downgrade base && alembic upgrade head`)
and runs `pytest` in Compose against a migrated Postgres, gated at
`--cov-fail-under=100` with zero warnings.

## Per-test rollback via a container override

`db_session` (`tests/conftest.py`) opens its own `AsyncConnection`, begins a
transaction on it, then calls
`di_container.override(ioc.Database.database_engine, connection)` — every
provider downstream of `Database.database_engine` in the DI graph (sessions,
repositories, use cases, and `retrieve_user_handler`'s own ad-hoc session in
`app/api/auth.py`) now resolves against that one connection instead of the
real pooled engine. `database_resources.create_session` sets
`join_transaction_mode="create_savepoint"`, so every session opened against
that connection — whether by a fixture or by a route handler mid-request —
nests inside the outer transaction as a savepoint rather than committing past
it. Teardown does `if connection.in_transaction(): await
transaction.rollback()`, which discards every write the test made.

That `if` guard is fail-silent: it exists to tolerate tests that already
closed their own transaction, but if a session were ever able to commit the
*outer* transaction rather than nesting a savepoint under it, teardown would
skip the rollback without raising and the next test would see leaked state.
See `planning/deferred.md`.

`di_container` (`tests/conftest.py`) itself comes from the already-built
`app` fixture (`modern_di_litestar.fetch_di_container(app)`), so `db_session`
overrides the same container instance production request handling resolves
providers from — a request-scoped child container built during a test
(`tests/use_cases/conftest.py::request_container`) inherits the override.

`tests/test_main.py::test_db_session_insert_is_visible_within_test` and
`test_db_session_rolls_back_between_tests` are a paired proof of this
mechanism: the first inserts a user and commits (on the fixture's own
session, inside the savepoint), the second asserts the table is empty. The
pair only proves rollback if pytest runs them in file order — running the
second alone (`-k test_db_session_rolls_back_between_tests`) passes
vacuously, since an empty table before any insert looks identical to a
successfully rolled-back one. See `planning/deferred.md`.

## DI providers as pytest fixtures

`tests/use_cases/conftest.py` calls `modern_di_pytest.expose(ioc.Repositories,
ioc.UseCases, container_fixture="request_container")` once, which generates
one pytest fixture per provider on both groups, named after the class
attribute (`create_chat_use_case`, `messages_repository`, …). Every
repository or use case added to `app/ioc.py` becomes an injectable test
fixture automatically — no test file hand-assembles a use case's dependency
graph. `request_container` itself is a child container built at
`modern_di.Scope.REQUEST`, depending on `db_session` (via an unused parameter
that forces the engine override to run first).

Layered fixtures build on top: `alice`/`bob`/`carol` (users via
`UserFactory`, a `polyfactory.SQLAlchemyFactory`), `direct_chat` (a real
`CreateChatUseCase` call between alice and bob), `alice_message` (a real
`CreateMessageUseCase` call), and `send` — a callable that stamps a fresh
`idempotency_key` per invocation, so ordinary test bodies never collide with
each other on retries.

## API-level tests

`tests/conftest.py::client` runs the real `build_app()` output through
`httpx.ASGITransport` plus `asgi_lifespan.LifespanManager`, so these tests
exercise the actual route handlers, middleware, and DI wiring — not a stub.
`tests/api/*.py` drive it with plain `AsyncClient` calls and helper functions
(`register`, `login`, `create_direct_chat`, `send`, shared from
`tests/api/helpers.py` and imported with a leading-underscore alias per the
local call-site convention) rather than fixtures, since the cookie-carrying
`client` instance is itself the shared state across a test's sequence of
requests.

## Simulating a DB race at the repository seam

`tests/use_cases/test_create_chat.py::_RacingChatsRepository` and
`tests/use_cases/test_create_message.py::_RacingMessagesRepository` subclass
the real repository and override exactly two methods: the pre-check read
(`fetch_direct_by_key` / `fetch_by_idempotency_key`) returns `None` once, as
if the winner's row weren't visible yet, then delegates to the real
implementation; `create` always raises `DuplicateKeyError`, as if the insert
collided with a row a concurrent request just committed. A second use case
instance is built by hand with the racing repository swapped in but sharing
the *same* `transaction`/session as the real winner call, so the winner's
already-committed row is visible to the loser's recovery re-read — this is
what lets a single-process test prove the two-request race without an actual
second connection. `_AlwaysDuplicateChatsRepository` is the companion negative
case: `create` always raises, with no direct-chat recovery path available
(group chat), proving the exception still propagates instead of being
funnelled into recovery it doesn't apply to.
