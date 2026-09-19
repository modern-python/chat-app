# Read-marker integrity

`MarkReadUseCase` verifies membership, verifies that `last_read_message_id`
names a message in that chat, then advances the marker in one UPDATE that sets
it to `GREATEST(COALESCE(last_read_message_id, 0), :requested)`. Computing the
maximum in Python from a prior read would let two concurrent `POST /read/` calls
interleave and the lower id win, the regression the monotonic rule exists to
prevent; `GREATEST` inside the UPDATE makes it atomic without a lock. Accepting
any id would let a client set its marker arbitrarily high and permanently zero
its own unread counts, and persisting self-inflicted corruption is worse than
refusing the request. Unread counts the messages above the marker whose
`user_id IS DISTINCT FROM` the member's; `IS DISTINCT FROM` rather than `!=` is
load-bearing, because system messages carry `user_id IS NULL` and `NULL != 1`
evaluates to NULL, silently dropping every one of them. Advancing to a lower id
is a silent no-op, since a replayed request is not a client mistake worth
reporting.
