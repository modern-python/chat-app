# Mutation requires membership, not just authorship

`fetch_message_for_author` (`app/use_cases/message_authorization.py`) is the one
definition of the check order shared by `EditMessageUseCase` and
`DeleteMessageUseCase`: load the message (`404` if absent), verify the actor is
a member of its chat (`403`), then verify the actor is the author (`403`).
Authorship alone shipped first and left every authenticated user able to `PATCH`
or `DELETE` an arbitrary message id in a chat they had no visibility into, and
to distinguish "does not exist" from "exists, not mine" for it; authorship
happens to block the ordinary case, which is why the first round of tests passed
identically with and without the membership check. The rule is pinned by a test
that constructs the one state where the two disagree, deleting the author's
`chat_members` row. A non-member still learns whether a message id exists,
because the message must be loaded before its chat is known, and that residual
is accepted deliberately, mirroring `FetchChatUseCase` returning `403` rather
than pretending the chat does not exist.
