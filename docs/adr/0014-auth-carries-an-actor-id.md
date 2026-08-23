# Authentication carries an actor id, not a user row

**Decision:** `retrieve_user_handler` resolves an `Actor` — a frozen dataclass
holding the `id` proved by the JWT — from `token.sub` alone, reading no row.

Auth middleware runs before request-scoped DI exists, so anything it loads must
come from a session it opens and closes itself. Loading the user row there cost
a second DB session per authenticated request against `db_pool_size=5` /
`db_max_overflow=0`, and handed every use case a detached ORM instance from a
closed session — safe only because every column happened to be loaded and
nobody mutated it. Against that, all ten reads of `actor` across
`app/use_cases/` were `actor.id`. `Actor` lives in `app/actor.py`, a top-level
module, so `app/use_cases/` never imports `app.api`.

## Rejected: loading the user row in middleware

The shape this replaces. Its one real benefit was that authentication proved
the user still existed; see Consequence for why that is not worth a session.
`GET /api/auth/me/` is the only consumer of the full row and now fetches it
through `FetchUserUseCase` on the request-scoped session, like every other
read. Reintroducing the lookup is invisible in API responses either way, which
is why the claim is pinned by
`test_retrieve_user_handler_resolves_an_actor_without_reading_the_database`
rather than by an endpoint test.

## Rejected: UUID or uuid7 user ids

Raised as the alternative to passing a bare integer around. There is one
writer, so there is no id-coordination problem to solve. `direct_key`
(`String(64)`) no longer fits two ids; three FK columns widen 8→16 bytes, one
of them indexed (`chat_members.user_id`); and `schemas.User.id` and
`member_ids` become a breaking API change. uuid7 is also the wrong tool for the
benefit usually wanted here — it publishes registration time in its first 48
bits. [`0001-sequence-ids-not-snowflakes.md`](0001-sequence-ids-not-snowflakes.md)
already carries the ordering argument for message ids.

## Rejected: an opaque public id

Deferred rather than refused. If opacity is ever wanted, the shape is the
two-id pattern — the BigInt PK stays internal, a separate opaque public id
faces outward — which is strictly additive on top of this decision. Adopting it
now would buy nothing and cost a second identifier to keep in agreement.

## Consequence

Authentication no longer proves the user exists. A token whose row is gone
authenticates: reads come back empty, writes hit the `messages.user_id` foreign
key. Nothing can reach that state today — there is no delete-user or
disable-user path — and the accepted cost is recorded in the invariant test's
docstring, not as a deferred item.

## Revisit trigger

A delete-user or disable-user path being added. It meets the same problem as
[`../../planning/deferred/2026-08-21-logout-does-not-revoke-jwt.md`](../../planning/deferred/2026-08-21-logout-does-not-revoke-jwt.md)
— a credential outliving what it names — and both should be solved once,
together.
