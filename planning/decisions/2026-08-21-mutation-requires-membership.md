---
summary: Editing and deleting a message requires chat membership as well as authorship; the check order is existence, membership, authorship.
---

# Mutation requires membership, not just authorship

`fetch_message_for_author` (`app/use_cases/message_authorization.py`) is the
single definition of the check order for both `EditMessageUseCase` and
`DeleteMessageUseCase`: load the message (`404` if absent), verify the actor is
a member of its chat (`403`), then verify the actor is the author (`403`).

## Rejected: authorship alone

Shipped first, and it left every authenticated user able to `PATCH`/`DELETE` an
arbitrary message id in a chat they had no visibility into, and to distinguish
"does not exist" from "exists, not mine" for it. Authorship happens to block the
ordinary case, which is why the first round of tests passed identically with and
without the membership check.

It was also inconsistent with the rest of the codebase: every other actor-scoped
use case gates on membership first. A reference application that applies its own
authorization rule unevenly teaches the wrong habit.

The check is proven by a test that constructs the one state where membership and
authorship disagree: the author's `chat_members` row is deleted, leaving her the
author of a message in a chat she is no longer in.

## Consequence

A non-member still learns whether a message id exists, because the message must
be loaded before its chat is known. That residual is accepted deliberately and
mirrors the decision that `FetchChatUseCase` returns `403` rather than
pretending the chat does not exist. See
`planning/deferred/2026-08-21-message-id-existence-404-vs-403.md`.

## Revisit trigger

A moderator or administrator role that must act on messages in chats it does not
belong to, or a requirement to close the existence oracle, which would mean
scoping the lookup through a `chat_members` join.
