---
summary: `SendMessageRequest.text` and `EditMessageRequest.text` independently declare the same length constraints, so a change to one silently doesn't affect the other.
---

# EditMessageRequest duplicates SendMessageRequest's text constraints

## Why it is open

Both `app/schemas/api.py::SendMessageRequest.text` and `EditMessageRequest.text`
independently declare `pydantic.Field(min_length=1, max_length=4000)`. A
change to one's bounds is silently not a change to the other's.

## Revisit trigger

The two are ever meant to diverge deliberately, or a bug report about edit
accepting/rejecting text that send doesn't (or vice versa).
