---
summary: Nothing in the test suite counts queries per request, so an N+1 regression in chat listing would keep `just test` green as long as the returned data stays correct.
---

# No query-count instrumentation

## Why it is open

Nothing in the test suite counts queries per request, so an N+1 regression in
the chat listing (e.g. `FetchChatsUseCase`'s bounded `last_message` lookup
regressing back to one query per chat) would keep `just test` green as long
as the returned data is still correct.

## Revisit trigger

A reported latency regression on `GET /api/chats/`, or before adding another
listing endpoint that joins per-row data.
