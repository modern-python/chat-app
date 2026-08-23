# Idempotency is scoped per chat

`messages` carries `UniqueConstraint("chat_id", "idempotency_key")`. The
pre-check lookup, the constraint, and the `DuplicateKeyError` recovery re-read
all filter on the same pair.

Idempotency is a property of an operation, and the operation is "send this
message *to this chat*". Two different chats are two different operations; a key
reused across them is not a retry of anything.

## Rejected: a global unique constraint on `idempotency_key`

Shipped first, and it made a reachable state look unreachable. With a global
constraint and a chat-scoped lookup, a cross-chat key reuse under concurrency
raises `DuplicateKeyError` from the insert, the scoped re-read misses, and
control reaches a guard whose only justification was "the unique constraint
guarantees a match here". That guarantee no longer held.

Keeping the constraint global while scoping only the lookup also meant a client
reusing a key across chats received the *other* chat's message and its intended
message was never written: a silent wrong-row return, which is worse than an
error.

The three surfaces must agree. Aligning the constraint with the lookup was the
cheaper direction, and it is the one that matches the domain.

## Consequence

The same client-generated key may legitimately appear in two chats. Callers that
assume global uniqueness of `idempotency_key` are wrong.

## Revisit trigger

A cross-chat operation that must be idempotent as a unit, such as forwarding one
message into several chats in a single request.
