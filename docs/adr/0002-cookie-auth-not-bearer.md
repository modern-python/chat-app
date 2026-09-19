# Cookie auth, not a bearer header

The JWT travels in a cookie (`JWTCookieAuth[Actor]`), not in an
`Authorization: Bearer` header, although every endpoint shipped today is REST,
where a bearer header is conventional and keeps the token out of the browser's
ambient credential store. The planned server-sent-events stream settles it: a
browser `EventSource` cannot set request headers, so a bearer-authenticated
stream needs a second mechanism, a query-string token or a pre-connect ticket,
which is two auth paths to keep in agreement and a token that lands in access
logs. Two costs are accepted deliberately: state-changing endpoints need CSRF
consideration, and `jwt_cookie_secure` is an explicit setting defaulting to
`False` rather than derived from `service_environment`, because a security
property inferred from an unrelated string is one nobody audits, and because
`True` by default would break the local HTTP development this application is
demonstrated with. The anonymous surface is four anchored `exclude` prefixes:
`^/docs`, `^/health`, `^/static` and `^/metrics`.
