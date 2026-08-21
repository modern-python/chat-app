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
   repositories would make that impossible. See `architecture/messages.md`
   and `architecture/chats.md` for the two hazards this creates around
   `Transaction.__aexit__`'s unconditional rollback-on-open-transaction
   behavior (returning a loaded ORM object from inside an uncommitted `async
   with self.transaction:` block detaches it).

## Commands

Recipes live in the `Justfile` — run `just --list` to see them; this section
only covers what isn't obvious from the recipe names.

Almost everything runs through Docker Compose: the app and Postgres come up
together, and running tests/migrations outside Docker is **not** the
supported path (`just install` and `just lint` are the exceptions — they run
on the host). Inside the container, raw commands look like `uv run pytest
...`, `uv run alembic ...`.

- `just test` cycles the DB (downgrade to `base`, upgrade to `head`) before
  pytest and tears the stack down before and after. Pass pytest args through,
  e.g. `just test tests/use_cases/test_create_chat.py -k race -x`.
- `just migration "message"` takes a **single positional argument** — not a
  `-m` flag — quoted so a multi-word message survives as one token (the
  recipe shell-quotes it with `quote()` before handing it to `alembic
  revision --autogenerate -m`). It runs against an already-upgraded DB; the
  recipe enforces that by upgrading first, so don't run autogen by hand.
- `just lint` runs `eof-fixer`, `ruff format`, `ruff check --fix`, then `ty
  check` — this project uses `ty`, not mypy; suppress with `# ty:
  ignore[<rule>]` (not `# type: ignore`).
- `just index` prints the planning change/decision listing; `just
  check-planning` validates `planning/changes/` and `planning/decisions/`
  frontmatter (CI-equivalent check, run before pushing a planning change).

Python is 3.14, dependencies managed by `uv`. The API is exposed on `:8000`.

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
parameters; each `app/api/endpoints/*.py` module declares them with
`modern_di_litestar.FromDI(...)` (wired centrally in `build_app`'s
`dependencies=` dict) so Litestar resolves them per-request. Provider scopes:
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
this line mutates a third-party base class at import time and has no
explanatory comment in the source; see `planning/deferred.md`. Repositories
are `SQLAlchemyAsyncRepositoryService[Model]` with a nested
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
the template predates this and hand-assembles dependencies instead. Full
detail, including the race-simulation pattern used to test the
concurrent-retry paths without a second real connection, is in
`architecture/testing.md`.

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
  to that list plus `build_app`'s `dependencies=` dict for any new use case.
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
  exceptions (`NotFoundError`, `DuplicateKeyError`, `ForeignKeyError`). Full
  mapping table and the one deliberate exception (login's `401` via Litestar's
  own `NotAuthorizedException`) are in `architecture/messages.md` and
  `architecture/auth.md`.
- `ruff` is configured with `select = ["ALL"]` and a line length of 120 —
  expect strict lint. Type-check with `ty`; use `# ty: ignore[<rule>]` for
  suppressions.
