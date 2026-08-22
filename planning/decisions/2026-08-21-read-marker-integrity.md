---
summary: The read marker advances only to a message in its own chat, and advances atomically via GREATEST so it can never move backwards.
---

# Read-marker integrity

`MarkReadUseCase` does three things in order: verify membership, verify that
`last_read_message_id` names a message in *that* chat, then advance the marker
with a single statement:

```sql
UPDATE chat_members
SET last_read_message_id = GREATEST(COALESCE(last_read_message_id, 0), :requested)
```

Unread is then `count(messages WHERE chat_id = ? AND id > COALESCE(marker, 0)
AND user_id IS DISTINCT FROM me AND deleted_at IS NULL)`.

`IS DISTINCT FROM` rather than `!=` is load-bearing: system messages carry
`user_id IS NULL`, and `NULL != 1` evaluates to NULL, which silently drops every
system message from the count. A regression test asserts this.

## Rejected: monotonicity enforced in Python

Read the member row, compute `max(current, requested)`, write it back. Two
concurrent `POST /read/` calls interleave and the lower id wins, which is
exactly the regression the monotonic rule exists to prevent. `GREATEST` in the
UPDATE makes it atomic without a lock.

## Rejected: accepting any id

Without the message-in-chat check a client can set its marker to an arbitrarily
large id and permanently zero its own unread counts. Persisting self-inflicted
data corruption is worse than refusing the request.

## Consequence

Marking read costs one extra lookup. Advancing to a lower id is a silent no-op
rather than an error, because a replayed or out-of-order request is not a client
mistake worth reporting.

## Revisit trigger

Per-device read markers, or a requirement to move a marker backwards
deliberately, such as "mark as unread".
