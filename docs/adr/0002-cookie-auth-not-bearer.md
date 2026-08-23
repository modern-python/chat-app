# Cookie auth, not a bearer header

**Decision:** The JWT travels in a cookie (`JWTCookieAuth[UsersTable]`), not in
an `Authorization: Bearer` header.

## Context

Every endpoint shipped today is REST, where a bearer header is the more
conventional choice and keeps the token out of the browser's ambient
credential store. The realtime follow-on adds a server-sent-events stream.

## Decision & rationale

A browser `EventSource` cannot set request headers — there is no API for it.
An SSE endpoint authenticated by a bearer header would therefore need a
second authentication mechanism (a token in the query string, or a
short-lived ticket exchanged before connecting), which means two code paths
to keep in agreement and a token that lands in access logs.

A cookie is sent automatically on the `EventSource` request, so the stream
authenticates identically to every other endpoint with no second path. That
this repository exists to demonstrate a realistic composition is what settles
it: carrying two auth mechanisms to avoid a cookie would be the less
realistic shape.

The cost is accepted deliberately: cookie auth needs CSRF consideration on
state-changing endpoints, and `jwt_cookie_secure` must be `True` behind
HTTPS — see
[`0003-explicit-cookie-secure-flag.md`](0003-explicit-cookie-secure-flag.md).

## Revisit trigger

The SSE endpoint being dropped from scope, or a non-browser client becoming
the primary consumer.
