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
superseded_by: 0014-its-slug
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

**Decision:** What was decided, in a sentence.

What the code actually does, and the constraint that forced it.

## Rejected: deriving it from the environment

Why it was not taken. Enough that a future explorer does not re-litigate it.

## Rejected: defaulting to True

One heading per alternative, named in the heading so it gets its own anchor.

## Consequence

The non-obvious downstream effect, including what this deliberately leaves
uncovered.

## Revisit trigger

The concrete signal that should reopen this decision.
```

`## Consequence` is optional. `## Revisit trigger` is required; a reviewer is
what enforces it.

## Where other facts go

This is one of four homes, and the narrowest. See
[`../../AGENTS.md`](../../AGENTS.md#where-a-fact-goes) for the admission check
that decides between code, an `INVARIANT:`-marked test, an ADR here, and a
GitHub issue for real work that is not scheduled.
