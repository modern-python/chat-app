# Auth

Litestar's `JWTCookieAuth[UsersTable]` (`app/api/auth.py`), configured with
`token_secret=settings.jwt_secret` and a 7-day default expiration
(`jwt_lifetime_seconds`). Cookie rather than bearer header: a browser
`EventSource` (planned for the realtime follow-on) cannot set an
`Authorization` header, so the cookie is the one auth variant every endpoint —
REST today, SSE later — can share identically.

## Registration and login

`POST /api/auth/register/` (`app/api/endpoints/auth.py::register`) runs
`RegisterUserUseCase`, which hashes the password with `argon2` (`app/security.py`)
inside its own transaction and returns `201` with the cookie set via
`jwt_cookie_auth.login`. A duplicate username raises `DuplicateKeyError` from
the unique constraint on `users.username`, mapped to `409` by the app-wide
handler — there is no auth-specific duplicate check.

`POST /api/auth/login/` runs `AuthenticateUserUseCase`, which looks the user up
by username and verifies the password hash. On failure — unknown username or
wrong password — it raises Litestar's own `NotAuthorizedException` (`401`),
not `app.exceptions.PermissionDeniedError`: this is the one place the
`litestar.exceptions` vocabulary is used directly, because login failure is
not an authorization decision to gate downstream of an already-identified
actor, it *is* the identification step. On success it returns `200` (not
`201` — nothing was created) with a fresh cookie.

`AuthenticateUserUseCase` hashes the submitted password even when the
username doesn't exist (`app/use_cases/authenticate_user.py`) specifically so
an unknown-username response isn't measurably faster than a
wrong-password response — skipping the argon2 work would turn login into a
username oracle.

`POST /api/auth/logout/` deletes the cookie and returns `204`. It does not
revoke the JWT: a token copied before logout stays valid for the rest of its
lifetime, because no `revoked_token_handler` is configured on
`jwt_cookie_auth`. See `planning/deferred.md`.

Both `register` and `login` opt out of the auth middleware with
`exclude_from_auth=True` on the handler, not through `jwt_cookie_auth`'s
`exclude` list — that list is reserved for path-shaped exclusions, each
anchored with `^` so a future route merely containing `/docs` as a path
segment isn't accidentally deauthenticated.

The anonymous surface is therefore exactly four prefixes: `/docs` and
`/health`, plus `/static` (Swagger's offline assets, served from there
because `swagger_offline_docs` is on — without the exclusion the docs page
loads but every asset request 401s) and `/metrics` (a Prometheus scrape
target must be reachable without a session cookie; it carries process and
request metrics, no user data).

## Request-time identity

`retrieve_user_handler` (`app/api/auth.py`) runs inside Litestar's auth
middleware, which executes *before* request-scoped DI is available. It cannot
resolve a use case or repository, so it resolves the app-scoped
`Database.database_engine` provider directly off the DI container
(`modern_di_litestar.fetch_di_container(connection.app)`) and opens its own
short-lived session through the same `database_resources.create_session`
factory the container uses, then closes it in a `finally`. This means every
authenticated request opens **two** sessions — one here, one for the
request-scoped repositories — against a pool sized `db_pool_size=5`,
`db_max_overflow=0`. See `planning/deferred.md`.

`Token.sub` is only guaranteed to be a non-empty string; `retrieve_user_handler`
converts it with `int(token.sub)` and returns `None` (→ `401` via the
middleware) on `ValueError` rather than letting a forged or malformed subject
crash the request. A validly signed token whose subject names a user that no
longer exists resolves to `None` from `session.get` the same way.

`GET /api/auth/me/` returns the authenticated `request.user` — no separate use
case, since the middleware has already loaded it.

## Configuration

`jwt_cookie_secure` (`app/settings.py`) defaults `False` so local `http://`
development still receives the cookie; it must be `True` in any deployment
served over HTTPS. `Settings.ensure_jwt_secret_is_configured`, called at the
top of `build_app`, raises `RuntimeError` at startup if
`service_environment != "local"` and `jwt_secret` is still the shipped
`INSECURE_JWT_SECRET` — the whole auth boundary is a token signed with that
secret, so running any non-local environment on the default would let anyone
forge a token for any `user.id`.
