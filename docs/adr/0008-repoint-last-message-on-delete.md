# Repoint last_message_id on delete

`DeleteMessageUseCase` soft-deletes the message and, when it was the chat's
`last_message_id`, repoints that column to the newest remaining message with
`deleted_at IS NULL`, or to `NULL` if none remains, committing both writes
together. The column therefore carries exactly one meaning, the newest
non-deleted message in this chat, and both the listing preview and the listing's
ordering (`coalesce(chats.last_message_id, 0) DESC`) read it. Adding
`deleted_at IS NULL` to the preview fetch is the smaller change and was
considered first, but it leaves two half-broken behaviours instead of one
correct one: the preview goes blank while older messages still exist, and the
chat keeps sorting by the deleted message's id, because ordering reads the same
column the preview stopped trusting. That filter is still present on the preview
relationship, as a self-defending invariant guard rather than as the mechanism.
`chats.last_message_id` stays a plain `BigInteger` rather than a foreign key,
because `chats` is created before `messages` exists and a circular constraint
pair would buy nothing at this scale.
