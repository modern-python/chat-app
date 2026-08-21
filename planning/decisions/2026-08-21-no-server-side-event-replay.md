---
status: accepted
summary: Reconnect recovery uses channel history plus a REST resync; no durable per-user event log honouring Last-Event-ID.
---

# No server-side event replay

On reconnect the client recovers in two layers. Fast path:
`RedisChannelsStreamBackend(history=N)` replays the last N events on the channel
at subscribe time. Correctness path: on every connect the client refetches
`GET /api/chats/` and `GET /api/chats/{id}/messages/?after_id=<highest seen>`
for the open chat, which resyncs state regardless of what the stream did.

SSE `id:` is set on message events, so the browser sends `Last-Event-ID` on
reconnect. It is treated as a hint that seeds the resync, not as a replay
cursor.

## Rejected: durable per-user event log

A table of events per user with monotonic ids, letting the SSE endpoint honour
`Last-Event-ID` by replaying exactly the missed range. This is the correct
answer for a system that must not drop an event.

Rejected because Litestar's channel history is a Redis stream keyed by its own
ids and is not addressable by ours, so honouring the header properly means
bypassing channel history entirely and owning the log. That is a second delivery
mechanism alongside the outbox, and the resync path already makes the client
correct at a fraction of the machinery.

## Consequence

A client disconnected longer than the channel history window recovers by
refetching rather than by replay. Correct, but O(state) instead of O(missed).

## Revisit trigger

Clients that cannot afford a full resync (mobile on metered connections), or an
event type whose effect cannot be reconstructed from current state.
