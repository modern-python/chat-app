---
summary: Auth middleware runs before request-scoped DI is available, so `retrieve_user_handler` opens its own session for the user lookup, separate from the request-scoped session used later.
---

# Every authenticated request opens two DB sessions

## Why it is open

Auth middleware runs before request-scoped DI is available, so
`retrieve_user_handler` (`app/api/auth.py`) opens its own short-lived session
for the user lookup, separate from the request-scoped session the resolved
use case's repositories use. That's two sessions per authenticated request
against `db_pool_size=5` / `db_max_overflow=0`.

## Revisit trigger

Before deploying this anywhere with real concurrent traffic — pool
exhaustion under load is the first thing to check if requests start timing
out waiting for a connection.
