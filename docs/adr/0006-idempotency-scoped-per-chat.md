# Idempotency is scoped per chat

`messages` carries `UniqueConstraint("chat_id", "idempotency_key")`, and the
pre-check lookup, the constraint and the `DuplicateKeyError` recovery re-read
all filter on that same pair. Idempotency is a property of an operation, and the
operation is "send this message to this chat", so two chats are two operations
and a key reused across them is not a retry of anything. A global constraint on
`idempotency_key` shipped first and made a reachable state look unreachable:
cross-chat key reuse under concurrency raised `DuplicateKeyError` from the
insert, the chat-scoped re-read missed, and control reached a guard whose only
justification was "the unique constraint guarantees a match here". Worse, a
client reusing a key across chats received the other chat's message while its
intended message was never written, a silent wrong-row return. The three
surfaces must agree, and aligning the constraint with the lookup was both the
cheaper direction and the one that matches the domain.
