# Logout revokes the token by its jti

Logout writes the token's `jti` and expiry to `revoked_tokens`, and
`revoked_token_handler` rejects any token listed there. A copy taken before
logout stops working, and the user's other sessions keep theirs. A token
version on `users` was rejected because one logout would end every session of
that user, and short-lived tokens with refresh because they replace the whole
auth model. The cost is one primary-key lookup per authenticated request, on a
session the middleware closes before the handler opens its own, so a request
still holds one pooled connection at a time. That lookup is the read
[ADR-0010](0010-auth-carries-an-actor-id.md) kept out of authentication; the
user row is still never loaded. A token without a `jti`, which includes every
token issued before this change, gets a 401. Each logout prunes expired rows,
so the table holds at most a token lifetime of logouts.
