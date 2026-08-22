# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`chat-app` was bootstrapped from `litestar-sqlalchemy-template`. It is **not**
the template with new routes — three things below differ from what the
template teaches, and getting any of them wrong by pattern-matching on the
template breaks the transaction model or the DI wiring.

## The three things most likely to be got wrong

1. **`modern-di` 3.x uses `cache=`, not `cache_settings=`.** Providers that
   need a finalizer or app-scope caching pass `cache=providers.CacheSettings(finalizer=...)`
   (see `app/ioc.py::Database.database_engine`). The template predates this
   API; do not copy `cache_settings=` from memory or from an older `modern-di`
   example.
2. **Repositories run `auto_commit=False`.** Every `*_repository` provider in
   `app/ioc.py` is constructed with `kwargs={"session": ..., "auto_commit":
   False}` — the opposite of the template's `auto_commit=True`. A repository
   here never commits on its own.
3. **Use cases own the transaction boundary, not repositories.** Every use
   case that writes wraps its work in `async with self.transaction:` (a
   `db_retry.Transaction`) and calls `await self.transaction.commit()`
   explicitly once every write that must land together has been made — e.g.
   `CreateMessageUseCase` commits the new message row and the
   `chats.last_message_id` update together. This exists because a single
   operation can span more than one repository write and they must succeed or
   fail as a unit; giving that back to individually auto-committing
   repositories would make that impossible. This creates a hazard around
   `Transaction.__aexit__`'s unconditional rollback-on-open-transaction
   behavior (returning a loaded ORM object from inside an uncommitted `async
   with self.transaction:` block detaches it).

## Commands

Recipes live in the `Justfile` — run `just --list` to see them; this section
only covers what isn't obvious from the recipe names.

Almost everything runs through Docker Compose: the app and Postgres come up
together, and running tests/migrations outside Docker is **not** the
supported path (`just install`, `just lint`, `just index`, `just
check-planning` and `just check-links` are the exceptions — they run on the
host). Inside the container, raw commands look like `uv run pytest ...`, `uv
run alembic ...`.

- `just test` cycles the DB (downgrade to `base`, upgrade to `head`) before
  pytest and tears the stack down before and after. Pass pytest args through,
  e.g. `just test tests/use_cases/test_create_chat.py -k race -x`.
- `just test-migrations` runs the `pytest-alembic` suite (`tests/migrations/`):
  single head, upgrade, per-revision up/down consistency, and
  model-definitions-match-DDL — the last being `alembic check` as a test. That
  directory is excluded from `just test` (`--ignore` in `addopts`, and from
  `coverage`'s `omit`) because it cycles the schema out from under the
  transaction-rollback fixture, so it needs the `--override-ini=addopts=` the
  recipe passes. CI runs both.
- Enum columns are native Postgres enums, and `alembic-postgresql-enum` is
  imported by `migrations/env.py` for its autogenerate hooks — that is what
  renders `CREATE TYPE` / `ALTER TYPE ... ADD VALUE` / `op.sync_enum_values`
  instead of silently missing them. Add or rename an enum value and
  `just migration` writes the type change for you.
- `just migration "message"` takes a **single positional argument** — not a
  `-m` flag — quoted so a multi-word message survives as one token (the
  recipe shell-quotes it with `quote()` before handing it to `alembic
  revision --autogenerate -m`). It runs against an already-upgraded DB; the
  recipe enforces that by upgrading first, so don't run autogen by hand.
- `just lint` runs `eof-fixer`, `ruff format`, `ruff check --fix`, then `ty
  check` — this project uses `ty`, not mypy; suppress with `# ty:
  ignore[<rule>]` (not `# type: ignore`).
- `just index` prints the deferred/decision listing; `just check-planning`
  validates `planning/deferred/` and `planning/decisions/` frontmatter (and
  that every deferred item carries a revisit trigger); `just check-links`
  validates every relative Markdown link and heading anchor in the repo.

Python is 3.14, dependencies managed by `uv`. The API is exposed on `:8000`.

## Workflow

**The spec for a change is its PR body**, not a committed file.
`.github/PULL_REQUEST_TEMPLATE.md` carries the shape (why, design, non-goals,
verification); it is reviewed with the diff. There is no change file and no lane
to choose. A trivial PR (typo, dep bump, formatter) deletes the template and
ships a conventional-commit title.

Two things outlive the PR and are committed under `planning/`: an alternative
**rejected** with reasoning goes to `planning/decisions/`, and real work **not
scheduled** goes to `planning/deferred/` (self-contained, with a revisit
trigger). There is no capability-page home — the living truth about behaviour is
the code and its `INVARIANT:`-marked tests, and a behaviour change is reviewed
with the diff, not promoted to a page. See `planning/README.md` for the full
convention, including the admission check that decides where a given fact
belongs.

An invariant is a test whose name is the claim, with a docstring opening
`INVARIANT:` and a second paragraph naming what breaks it. Applied to new
claims; the existing suite is not retrofitted.

## Architecture

**Stack**: Litestar + SQLAlchemy 2 (async) + advanced-alchemy + Alembic +
Postgres 17 + Granian (ASGI server) + `modern-di` (IoC) + `lite-bootstrap`
(observability/CORS/Sentry/OTel wiring) + `db-retry` (transaction boundary +
retry decorator).

**Request flow**: `app/api/__main__.py` → `granian` → `app.api.app:build_app`
(factory) → `LitestarBootstrapper` from `lite-bootstrap` wraps a
`litestar.Litestar` with OpenTelemetry (asyncpg + SQLAlchemy instrumentors,
with `AsyncPGInstrumentor(capture_parameters=False)` so argon2 password
hashes bound as INSERT parameters never reach the OTel collector), Sentry,
CORS, Swagger, etc., based on `Settings.api_bootstrapper_config`.
`build_app` also calls `settings.ensure_jwt_secret_is_configured()` first,
which raises at startup if a non-local environment is still running the
default JWT secret.

**Dependency injection** (`app/ioc.py`): one `modern_di.Container` built from
`ALL_GROUPS = [Database, Repositories, UseCases]`, attached via
`modern_di_litestar.ModernDIPlugin`. Route handlers receive use cases as
parameters typed `NamedDependency[SomeUseCase]`; nothing wires them by hand.
`build_app` passes `autowired_groups=[ioc.UseCases]` to the plugin, which
registers one Litestar dependency per provider on that group, named after the
provider attribute (`create_chat_use_case`, ...). `Database` and `Repositories`
are deliberately **not** autowired — a route handler has no business resolving
a session, a transaction or a repository directly. Provider scopes:
- `Database.database_engine` — app-scoped factory, `cache=` finalizer disposes
  the engine.
- `Database.database_session` — request-scoped, finalizer closes the session.
- `Database.transaction` — request-scoped `db_retry.Transaction`, the object
  every write-side use case wraps its commit in.
- `Repositories.*` — request-scoped, `auto_commit=False` (see above).
- `UseCases.*` — request-scoped, one class per operation.

**Persistence**: Models inherit `advanced_alchemy.base.BigIntAuditBase` /
`BigIntBase`. `app/database/tables.py` shares metadata with
`orm.DeclarativeBase.metadata` (`METADATA = orm_registry.metadata;
orm.DeclarativeBase.metadata = METADATA`) so Alembic autogen sees everything —
this line mutates a third-party base class at import time, because otherwise
models register on `orm.DeclarativeBase`'s own metadata and autogen sees no
tables at all. Repositories are
`SQLAlchemyAsyncRepositoryService[Model]` with a nested
`BaseRepository(SQLAlchemyAsyncRepository[Model])`, same shape as the
template, but every service here is constructed with `auto_commit=False`.

**Test isolation** (`tests/conftest.py`): `db_session` opens a connection,
starts a transaction, then **overrides** `Database.database_engine` in the DI
container to return that connection; `create_session`'s
`join_transaction_mode="create_savepoint"` is what makes every session opened
against it — fixture or route handler — nest as a savepoint instead of
committing past the outer transaction. Teardown rolls the outer transaction
back. `app`/`client` fixtures build the real app and run it through
`httpx.ASGITransport` + `asgi_lifespan.LifespanManager`.
`modern_di_pytest.expose(ioc.Repositories, ioc.UseCases,
container_fixture="request_container")` (`tests/use_cases/conftest.py`)
exposes every repository/use case provider as a same-named pytest fixture —
the template predates this and hand-assembles dependencies instead. The
race-simulation pattern used to test the concurrent-retry paths without a second
real connection is the `_Racing*Repository` classes in
`tests/use_cases/test_create_chat.py` and `tests/use_cases/test_create_message.py`;
the invariant each one pins is in the `INVARIANT:` docstring on the test that uses it.

**Migrations**: `migrations/env.py` reads the shared `METADATA` and rewrites
the DSN driver from `postgresql+asyncpg` → `postgresql` (Alembic uses sync
psycopg2). Always run autogen against an upgraded DB — `just migration`
enforces this.

**Settings** (`app/settings.py`): `pydantic_settings.BaseSettings` reads from
env vars (see `docker-compose.yml`). `api_bootstrapper_config` builds the
`LitestarConfig` consumed by `lite-bootstrap`. `jwt_cookie_secure` defaults
`False` for local `http://` development and must be `True` behind HTTPS.

## Conventions

- Routes live in `app/api/endpoints/`, one module per resource (`auth.py`,
  `chats.py`, `messages.py`), each exposing its own `ROUTER` (`litestar.Router`,
  prefix `/api`). `app/api/app.py::build_app` registers them all via
  `route_handlers=[auth_endpoints.ROUTER, chats_endpoints.ROUTER,
  messages_endpoints.ROUTER]`. Add a new resource by creating
  `app/api/endpoints/<name>.py`, defining handlers + a `ROUTER`, and adding it
  to that list. A new use case needs no wiring beyond its `ioc.UseCases`
  provider: `autowired_groups` exposes it under the provider's own name.
  Handlers that need the caller annotate the request `app.api.auth.AuthedRequest`
  and pass `actor=request.user` explicitly; every use case `__call__` is
  keyword-only.
- Use cases live in `app/use_cases/`, one `@dataclasses.dataclass(kw_only=True,
  frozen=True, slots=True)` per operation with an async `__call__` decorated
  `@db_retry.postgres_retry`. Shared authorization logic that more than one
  use case needs (e.g. the author-and-member gate for edit/delete) lives in a
  plain module-level function, not a base class — see
  `app/use_cases/message_authorization.py`.
- Pydantic schemas in `app/schemas/api.py` use `from_attributes=True` (via
  `Base`) so they validate directly from ORM instances
  (`schemas.X.model_validate(orm_instance)`). Collection responses go through
  `Collection[T].from_models(...)` (e.g. `schemas.Messages`, `schemas.Chats`).
- Domain exceptions (`app/exceptions.py`: `PermissionDeniedError`,
  `ValidationError`, `ConflictError`) are registered as handlers in
  `build_app`'s `exception_handlers` dict alongside the `advanced_alchemy`
  exceptions (`NotFoundError`, `DuplicateKeyError`, `ForeignKeyError`). Every
  mapping, and why login's `401` deliberately uses Litestar's own
  `NotAuthorizedException` instead, is described in
  `planning/decisions/2026-08-21-domain-error-vocabulary.md`.
- **Comments.** None, unless the code would read as a bug without one; then a
  single line. Rationale, design decisions and "why not X" belong in
  `planning/decisions/` and the PR body, never in the source — those are where
  such reasoning is reviewed and kept, and a comment restating it goes stale in
  place.
  What survives in `app/` today is the whole permitted category: a setting that
  looks arbitrary (`join_transaction_mode`, `populate_existing`,
  `capture_parameters=False`), an `orm.foreign()` on a column with no
  `ForeignKey`, a `return` from inside a transaction block, discarded work that
  is not dead code (`AuthenticateUserUseCase`'s hash-anyway). Alembic's own
  `# ###` autogenerate markers stay — they are regenerated on every migration.
- `ruff` is configured with `select = ["ALL"]` and a line length of 120 —
  expect strict lint. Type-check with `ty`; use `# ty: ignore[<rule>]` for
  suppressions.

## Vocabulary

A term is listed only when there is a synonym to reject, or a meaning subtle
enough that code and docs must agree on it.

- **Chat** — a row in `chats`: a type (`direct` or `group`), an optional title,
  its creator, and a pointer to its newest non-deleted message. *Avoid:*
  conversation, room, thread.
- **Direct chat** — a chat between exactly two users, identified by `direct_key`,
  the canonical `min(user_id):max(user_id)` string under a unique constraint.
  That key is what makes opening one twice an upsert instead of a read-then-race.
  *Avoid:* DM, 1:1.
- **Member** — the `(chat_id, user_id)` row granting access to a chat, plus that
  user's read marker. Necessary for every read or write on a chat; not
  sufficient for editing or deleting a message. *Avoid:* participant, subscriber.
- **Idempotency key** — the client-supplied UUID on a send, unique per
  `(chat_id, idempotency_key)`. Scoped to one chat, because the key identifies a
  retry of "send this message to this chat". *Avoid:* dedupe key, request id.
- **Unread** — a count computed at read time against one marker per member, not
  a set of per-message receipt rows. *Avoid:* unseen, badge count.
- **Cursor** — a message id passed as `before_id` or `after_id`. The two are
  mutually exclusive on one request. *Avoid:* page token, offset.
- **Read marker** — a member's `last_read_message_id`, the highest id they have
  acknowledged. Advances only forward, via `GREATEST` inside the UPDATE. *Avoid:*
  read receipt, watermark.
