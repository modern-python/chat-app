# Architecture

The living truth about what `chat-app` does **now** — one file per capability,
updated by hand whenever a change ships. The *why* and *how it got here* live
in [`../planning/changes/`](../planning/changes/), and decisions deliberately
taken (including options rejected) in
[`../planning/decisions/`](../planning/decisions/); this directory is the
present.

These files carry **no frontmatter** — they are prose, dated by git.

## Capabilities

- [auth.md](auth.md) — registration, login, the JWT cookie, `retrieve_user_handler`.
- [chats.md](chats.md) — direct/group chats, the direct-chat upsert, membership.
- [messages.md](messages.md) — idempotent send, cursor pagination, edit/delete authorization, unread counts.
- [testing.md](testing.md) — the per-test rollback fixture, DI-fixture exposure, the race-simulation pattern.
- [glossary.md](glossary.md) — the domain's ubiquitous language.

## Promotion rule

Shipping a change hand-edits the affected capability file(s) here to match the
new reality, in the same PR as the code. The change file stays in place under
[`../planning/changes/`](../planning/changes/) — no folder move.
