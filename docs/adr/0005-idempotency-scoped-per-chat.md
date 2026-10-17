# Idempotency is scoped per chat

`messages` carries `UniqueConstraint("chat_id", "idempotency_key")`, and the
send's `ON CONFLICT` names that constraint. Idempotency belongs to the operation
"send this message to this chat", so a key reused in another chat is a different
operation, not a retry. A global constraint on `idempotency_key` shipped first.
A client that reused a key across chats got the other chat's message back, and
the message it meant to send was never written.
