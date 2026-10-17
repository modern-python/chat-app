# Read-marker integrity

`MarkReadUseCase` rejects a `last_read_message_id` that does not name a message
in that chat with a `400`, and moving the marker to a lower id is a silent
no-op. Accepting any id would let a client set its marker arbitrarily high and
permanently zero its own unread counts, and storing self-inflicted corruption is
worse than refusing the request. A lower id usually comes from a replayed or
reordered request, which is not a client mistake worth reporting, so it gets the
current marker back instead of an error.
