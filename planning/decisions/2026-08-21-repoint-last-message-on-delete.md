---
status: accepted
summary: Soft-deleting a chat's newest message repoints chats.last_message_id in the same transaction, rather than filtering the deleted row out of the listing preview.
---

# Repoint last_message_id on delete

`DeleteMessageUseCase` soft-deletes the message and, if it was the chat's
`last_message_id`, repoints that column to the newest remaining message with
`deleted_at IS NULL`, or to `NULL` if none remains. Both writes commit together.

The column therefore has one meaning: the newest non-deleted message in this
chat. The listing preview and the listing's ordering
(`coalesce(chats.last_message_id, 0) DESC`) both read it, and both stay correct.

## Rejected: filtering the preview query instead

Adding `deleted_at IS NULL` to the preview fetch is the smaller change and was
considered first. It leaves two half-broken behaviours instead of one correct
one: the preview goes blank while older messages still exist, and the chat
continues to sort by the deleted message's id, because ordering reads the same
column the preview stopped trusting.

The filter is still present on the preview fetch, but as a self-defending
invariant guard rather than as the mechanism.

## Consequence

Deleting the newest message costs one extra query. `chats.last_message_id`
remains a plain `BigInteger` rather than a foreign key, because `chats` is
created before `messages` exists and a circular constraint pair would buy
nothing at this scale.

## Revisit trigger

A hard-delete path, a bulk delete, or any other writer of
`chats.last_message_id` that would need the same repointing logic.
