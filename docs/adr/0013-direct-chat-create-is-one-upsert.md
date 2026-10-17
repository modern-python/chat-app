# A direct chat is created with one upsert

`ChatsRepository.get_or_create_direct` uses the statement shape from
[0012](0012-message-send-is-one-upsert.md): `INSERT ... ON CONFLICT (direct_key)
DO UPDATE SET direct_key = EXCLUDED.direct_key RETURNING ..., xmax = 0`. A
concurrent request for the same pair waits on the row lock and gets the
winner's chat. Members are inserted only when the chat is new, and
`fetch_with_members` loads the result inside the same transaction. This replaces
the `DuplicateKeyError` recovery in
[0005](0005-upsert-via-duplicate-key-recovery.md), whose re-read ran outside the
retried transaction. The cost lands on replay, the common path: opening an
existing DM now takes three statements (upsert, SELECT, selectin) where the
pre-check took two. Keeping replay at two meant inserting or selecting members
by hand and attaching them to the viewonly relationship, which was rejected as
more machinery than one statement is worth.
