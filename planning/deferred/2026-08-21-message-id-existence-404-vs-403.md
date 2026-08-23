---
summary: A non-member issuing `PATCH`/`DELETE /api/messages/{id}/` gets `404` for a nonexistent id and `403` for one that exists but isn't theirs, leaking whether the id is real.
---

# Message id existence is distinguishable via 404-vs-403

## Why it is open

A non-member issuing `PATCH`/`DELETE /api/messages/{id}/` gets `404` for an
id that doesn't exist and `403` for one that does but belongs to a chat
they're not in — the two status codes leak whether the id is real. Accepted
deliberately: it mirrors the spec's own decision that `FetchChatUseCase`
returns `403` for a chat the actor isn't a member of rather than pretending
the chat doesn't exist (see `../../docs/adr/0006-mutation-requires-membership.md`), and checking membership
before authorship on every message use case keeps that posture consistent
rather than making message mutation the one place that hides existence.

## Revisit trigger

A threat model where message-id enumeration by a non-member is a real
concern (e.g. ids that encode something sensitive).
