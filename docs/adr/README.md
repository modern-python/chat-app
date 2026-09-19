# Architecture decision records

One file per decision taken, especially the options **rejected**, so reviews do
not re-litigate them. The directory listing is the index: there is no generated
listing and no `summary` frontmatter. Nothing validates the set mechanically;
the standard below is held up by review.

## Numbering

Numbers run contiguously from `0001` and mean nothing beyond identity. A new
ADR takes the next free number. When the set is reshaped, because records were
merged or dropped, the survivors are renumbered in their original order so the
sequence stays contiguous, and every citation moves in the same change:
`tests/test_adr_citations.py` fails on a `docs/adr/` path that no longer
resolves.

## Status lives in the frontmatter, or nowhere

An ADR with no frontmatter is **accepted**. A decision that is re-argued and
replaced is superseded, not deleted, so the earlier reasoning stays readable. A
record that no longer passes the admission test below is deleted outright; git
history keeps it.

When a later ADR supersedes an earlier one, add to the earlier file:

```yaml
---
superseded_by: 0010-its-slug
---
```

## The admission test

All three must be true, or it is not an ADR:

1. **Hard to reverse.** Changing your mind later carries a real cost.
2. **Surprising without context.** A reader will look at the code and wonder why
   it was done this way.
3. **A real trade-off.** There were genuine alternatives and one was picked for
   specific reasons.

## Template

```md
# One-line capitalized title

One paragraph: what the context is, what was decided, and why, naming the
rejected alternative where the rejection is not obvious. Typically 60 to 150
words.
```

That is the whole record: no `**Decision:**` line, no `## Rejected:` headings,
no `## Consequence`, no `## Revisit trigger` section. A consequence or a
revisit condition earns a sentence in the paragraph only when it is the real
boundary of the decision; a reviewer is what enforces that.

## Where other facts go

This is one of four homes, and the narrowest. Anything an agent can read out of
`app/` stays in the code; a claim a wrong change could silently break belongs in
an `INVARIANT:`-marked test; a rejected alternative, with the reasoning that
would otherwise be re-litigated, is an ADR here; real work that is not scheduled
is a GitHub issue. [`../../AGENTS.md`](../../AGENTS.md#workflow) defines the
last two.
