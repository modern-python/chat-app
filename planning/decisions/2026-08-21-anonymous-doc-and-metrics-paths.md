---
summary: The auth exclude list carries four anchored prefixes — /docs, /health, /static and /metrics — and nothing else.
---

# The anonymous surface is four prefixes

`jwt_cookie_auth`'s `exclude` list holds `^/docs`, `^/health`, `^/static` and
`^/metrics`. Every pattern is anchored, because Litestar joins them into one
alternation and matches it with an unanchored `findall`: an unanchored `/health`
would silently deauthenticate any future route containing that substring, such
as `/api/chats/{id}/health`.

`/static` is Swagger's own offline asset directory, mounted because
`swagger_offline_docs` is on. Without the exclusion the docs page returns `200`
and then every asset request returns `401`, so the page loads and fails to
render for anonymous visitors. `/metrics` is a Prometheus scrape target,
registered because `prometheus_client` ships in `lite-bootstrap[litestar-all]`;
a scrape target behind a session cookie is a broken feature, and the endpoint
exposes process and request metrics, not user data.

Route-level exemptions are expressed differently: `register` and `login` use
`exclude_from_auth=True` on the handler. Path-shaped exclusions go in the list;
route-shaped ones go on the route. Each policy has one home.

## Rejected: leaving /metrics authenticated

Defensible, and it is what shipped initially by omission. But it silently
disables a feature the bootstrapper registers, and the standard hardening for
metrics is a separate port or a network ACL, which is a deployment concern this
repository does not model.

## Consequence

Anything served under those four prefixes is public. A future route must not be
placed under them casually.

## Revisit trigger

Metrics carrying anything user-identifying, a deployment that exposes `/metrics`
to the internet, or Litestar changing where Swagger's offline assets are mounted.
