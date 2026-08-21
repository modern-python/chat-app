# Deferred

Real-but-unscheduled items. Each carries a revisit trigger.

## Litestar channels: subscriber orphaned on mid-subscribe disconnect

`ChannelsPlugin.subscribe()` registers the subscriber into `_channels` before
awaiting the history fetch, so a client disconnecting mid-subscribe leaves a
registered subscriber that is never unsubscribed. Upstream:
[litestar#4871](https://github.com/litestar-org/litestar/issues/4871).

`rchat` works around it by reordering the operations, which requires reaching
into `plugin._subscriber_class`, `plugin._channels`, and `plugin._backend`. Not
shipped here: a reference repository demonstrating private-attribute access
teaches the wrong lesson, and the leak is inert at demo scale.

**Revisit trigger:** upstream fix released, or a deployment where connection
churn is high enough for the leak to matter.

## Litestar channels: empty channel entries retained after unsubscribe

`unsubscribe` removes the subscriber but leaves the now-empty `set()` and its key
in `self._channels`. With per-user channel names that dict grows by one entry per
distinct user that ever connects, in a singleton that lives for the whole
process. Upstream:
[litestar#4867](https://github.com/litestar-org/litestar/issues/4867).

`rchat`'s `PruningChannelsPlugin` overrides the public `unsubscribe` to drop
empty entries, so this one needs no private access. Still not shipped, for
symmetry with the item above and because the growth is bounded by distinct users
in a demo.

**Revisit trigger:** upstream fix released, or the app being run anywhere with a
non-trivial user population.

## Presence beyond a TTL key

Presence is planned as a Redis key with a TTL refreshed by the SSE heartbeat.
This reports "has an open stream", not "is looking at this chat", and a client
killed between heartbeats stays online until expiry.

**Revisit trigger:** the demo needing per-chat presence or accurate last-seen.

## Per-test rollback is fail-silent on an unexpected commit

The `if connection.in_transaction():` guard in `tests/conftest.py`'s
`db_session` teardown skips the rollback without error whenever the outer
transaction is already closed. It exists to tolerate tests that legitimately
closed their own transaction, but it can't distinguish that from a session
somewhere having committed the outer transaction instead of nesting a
savepoint under it — that failure mode would leak state into the next test
with no diagnostic.

**Revisit trigger:** a test suite flake that looks like cross-test state
leakage, or before adding any code path that opens a session without going
through `database_resources.create_session`.

## Isolation test pair is order-dependent

`tests/test_main.py::test_db_session_insert_is_visible_within_test` and
`test_db_session_rolls_back_between_tests` together prove the per-test
rollback fixture, but only when pytest runs them in file order: the first
inserts and commits, the second asserts the table is empty. Run the second
alone (e.g. `-k test_db_session_rolls_back_between_tests`) and it passes
vacuously — an empty table before any insert is indistinguishable from a
correctly rolled-back one.

**Revisit trigger:** test order ever becomes non-deterministic (parallel
pytest execution, `pytest-randomly`), or before trusting `-k` output from just
this pair as proof the fixture works.

## Undocumented mutation of a third-party base class

`app/database/tables.py` sets `orm.DeclarativeBase.metadata = METADATA` at
import time, redirecting SQLAlchemy's shared declarative base onto
advanced-alchemy's registry so Alembic autogen sees every table. The line has
no comment explaining why it's there or what breaks if it's removed or
reordered relative to the model class definitions below it.

**Revisit trigger:** upgrading SQLAlchemy or advanced-alchemy across a major
version, or the next person who has to figure out why autogen stopped seeing
a table.

## Logout does not revoke the JWT

`POST /api/auth/logout/` deletes the cookie but the token itself stays valid
for the rest of its `jwt_lifetime_seconds` (7 days by default) if it was
copied out of the cookie beforehand — no `revoked_token_handler` is
configured on `jwt_cookie_auth`.

**Revisit trigger:** any deployment where a leaked/copied token is a realistic
threat model, or before shipping a "log out of all devices" feature.

## Every authenticated request opens two DB sessions

Auth middleware runs before request-scoped DI is available, so
`retrieve_user_handler` (`app/api/auth.py`) opens its own short-lived session
for the user lookup, separate from the request-scoped session the resolved
use case's repositories use. That's two sessions per authenticated request
against `db_pool_size=5` / `db_max_overflow=0`.

**Revisit trigger:** before deploying this anywhere with real concurrent
traffic — pool exhaustion under load is the first thing to check if requests
start timing out waiting for a connection.

## Message id existence is distinguishable via 404-vs-403

A non-member issuing `PATCH`/`DELETE /api/messages/{id}/` gets `404` for an
id that doesn't exist and `403` for one that does but belongs to a chat
they're not in — the two status codes leak whether the id is real. Accepted
deliberately: it mirrors the spec's own decision that `FetchChatUseCase`
returns `403` for a chat the actor isn't a member of rather than pretending
the chat doesn't exist (see `architecture/chats.md`), and checking membership
before authorship on every message use case keeps that posture consistent
rather than making message mutation the one place that hides existence.

**Revisit trigger:** a threat model where message-id enumeration by a
non-member is a real concern (e.g. ids that encode something sensitive).

## `EditMessageRequest` duplicates `SendMessageRequest`'s text constraints

Both `app/schemas/api.py::SendMessageRequest.text` and `EditMessageRequest.text`
independently declare `pydantic.Field(min_length=1, max_length=4000)`. A
change to one's bounds is silently not a change to the other's.

**Revisit trigger:** the two are ever meant to diverge deliberately, or a bug
report about edit accepting/rejecting text that send doesn't (or vice versa).

## No query-count instrumentation

Nothing in the test suite counts queries per request, so an N+1 regression in
the chat listing (e.g. `FetchChatsUseCase`'s bounded `last_message` lookup
regressing back to one query per chat) would keep `just test` green as long
as the returned data is still correct.

**Revisit trigger:** a reported latency regression on `GET /api/chats/`, or
before adding another listing endpoint that joins per-row data.
