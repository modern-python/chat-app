# Three domain exceptions, not one

`app/exceptions.py` defines `ChatAppError` with three subclasses, each mapped to
a status code by a handler registered in `build_app`: `PermissionDeniedError` to
`403` for authorization only, `ValidationError` to `400` for request shape ("a
direct chat must have exactly two distinct members"), and `ConflictError` to
`409` for state conflict, which today means editing a deleted message. The
initial design raised `PermissionDeniedError` for all three, and it is wrong
twice over: a body with three members in a direct chat is not a permissions
problem, and the author of a deleted message is authorized, so either inside a
"Permission denied" envelope tells the client to find credentials it already
has. Login failure is the mirror of that mistake, which is why `login` and
`GET /api/auth/me/` raise Litestar's `NotAuthorizedException`: a bad credential
is an identification failure, with no actor yet to authorize.
`advanced-alchemy`'s `NotFoundError`, `DuplicateKeyError` and `ForeignKeyError`
map to `404`, `409` and `400` with constant detail strings rather than
`str(exc)`, because an integrity error can carry bound parameters from another
row.
