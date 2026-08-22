---
summary: Logout deletes the cookie but does not revoke the JWT, which stays valid for the rest of its lifetime if it was copied beforehand.
---

# Logout does not revoke the JWT

## Why it is open

`POST /api/auth/logout/` deletes the cookie but the token itself stays valid
for the rest of its `jwt_lifetime_seconds` (7 days by default) if it was
copied out of the cookie beforehand — no `revoked_token_handler` is
configured on `jwt_cookie_auth`.

## Revisit trigger

Any deployment where a leaked/copied token is a realistic threat model, or
before shipping a "log out of all devices" feature.
