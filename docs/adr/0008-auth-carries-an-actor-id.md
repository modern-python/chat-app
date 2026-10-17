# Authentication carries an actor id, not a user row

`retrieve_user_handler` resolves an `Actor`, a frozen dataclass holding only the
id proved by the JWT, from `token.sub` alone, reading no row. Auth middleware
runs before request-scoped DI exists, so anything it loads comes from a session
it opens and closes itself: loading the user row there cost a second DB session
per authenticated request against `db_pool_size=5` and `db_max_overflow=0`, and
handed every use case a detached ORM instance from a closed session. Against
that, every read of `actor` across `app/use_cases/` is `actor.id`. Making the id
a UUID or uuid7 was rejected for the reason in
[ADR-0001](0001-sequence-ids-not-snowflakes.md), one writer and so no id
coordination to solve, and because it would overflow `direct_key`'s `String(64)`
and break the public `User` schema. The accepted cost is that authentication no
longer proves the user exists: a token whose row is gone still authenticates,
reads come back empty and writes hit the `messages.user_id` foreign key. Nothing
reaches that state today because there is no delete-user path, and adding one
reopens this.
