# Cookie security is an explicit setting

`Settings.jwt_cookie_secure` defaults to `False` and is passed straight to
`JWTCookieAuth(secure=...)`. Production must set it.

Litestar sets `httponly=True` and `samesite="lax"` for you, but leaves `secure`
as `None`, so without this setting a session JWT with a seven-day lifetime
travels over plain HTTP.

A companion guard lives in `Settings.ensure_jwt_secret_is_configured`, called as
the first statement of `build_app`: booting with the default `jwt_secret`
outside `service_environment="local"` raises rather than starting a service
whose every user's token is forgeable.

## Rejected: deriving it from the environment

`secure = service_environment != "local"` needs no new setting and is right by
default. It was rejected because a reader of a reference application should see
where the decision is made. A security property inferred from an unrelated
string is a property nobody audits, and the inference is silently wrong the
first time someone introduces an environment name the expression did not
anticipate.

## Rejected: defaulting to True

Correct for production and unusable for local development over HTTP, which is
how this application is demonstrated.

## Consequence

A deployment that forgets `JWT_COOKIE_SECURE` transmits session cookies in
clear. The startup guard covers the forged-token case but deliberately does not
cover this one, because there is no way to distinguish "HTTP because local" from
"HTTP by mistake" at boot.

## Revisit trigger

Adding HSTS or terminating TLS in-process, either of which would make `True` a
safe default.
