# A direct chat is created with one upsert, and members are attached by hand

`ChatsRepository.get_or_create_direct` uses the statement shape from
[0012](0012-message-send-is-one-upsert.md): `INSERT ... ON CONFLICT (direct_key)
DO UPDATE SET direct_key = EXCLUDED.direct_key RETURNING ..., xmax = 0`. A
concurrent request for the same pair waits on the row lock and gets the
winner's chat. Members then take one statement. A new chat inserts every member
in a single `INSERT ... RETURNING`, and a replay selects the chat's members.
`orm.attributes.set_committed_value` puts that list on the viewonly `members`
relationship. Calling `fetch_with_members` after the upsert would be simpler,
but replay is the common path, since every "open a DM with Bob" request after
the first is one. The upsert, a SELECT and a selectin load would cost a replay
three statements where the old pre-check took two. Attaching keeps a replay at
two statements and brings creation down from nine to two. Group chats have no
unique key, so they keep a plain insert and use the same member insert. This
supersedes the `DuplicateKeyError` recovery in
[0005](0005-upsert-via-duplicate-key-recovery.md).
