---
summary: Presence is planned as a Redis key with a TTL refreshed by the SSE heartbeat, which reports stream-open rather than actively-viewing.
---

# Presence beyond a TTL key

## Why it is open

Presence is planned as a Redis key with a TTL refreshed by the SSE heartbeat.
This reports "has an open stream", not "is looking at this chat", and a client
killed between heartbeats stays online until expiry.

## Revisit trigger

The demo needing per-chat presence or accurate last-seen.
