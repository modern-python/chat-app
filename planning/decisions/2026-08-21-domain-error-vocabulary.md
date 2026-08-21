---
status: accepted
summary: Domain failures are split across PermissionDeniedError (403), ValidationError (400) and ConflictError (409) rather than expressed as authorization failures.
---

# Three domain exceptions, not one

`app/exceptions.py` defines `ChatAppError` and three subclasses, each with a
handler registered in `build_app`:

- `PermissionDeniedError` to `403`, for authorization only: the caller may not
  perform this action on this resource.
- `ValidationError` to `400`, for request shape: "a direct chat must have
  exactly two distinct members", "before_id and after_id are mutually
  exclusive", "limit must be at least 1", "that message is not in this chat".
- `ConflictError` to `409`, for state conflict: editing a message that has been
  deleted.

`advanced-alchemy`'s `NotFoundError` maps to `404`, `DuplicateKeyError` to
`409`, and `ForeignKeyError` to `400` with a constant detail string. Litestar
handles `NotAuthorizedException` natively as `401`.

## Rejected: PermissionDeniedError for everything

The initial design raised `PermissionDeniedError` for malformed request bodies
and for state conflicts as well as for authorization. It is the shape a reader
copies, and it is wrong twice over: a body with three members in a direct chat
is not a permissions problem, and the author of a deleted message *is*
authorized. Returning either inside a "Permission denied" envelope tells the
client to go find credentials it already has.

## Consequence

Every new use case must pick a category deliberately. Handlers must not
stringify the underlying exception when the query carried credential material,
which is why `DuplicateKeyError` and `ForeignKeyError` return constant details.

## Revisit trigger

A fourth failure category that fits none of the three, or an `RFC 9457`
problem-details response format, which would restructure all of them.
