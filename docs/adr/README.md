# Architecture decision records

One file per decision taken, especially the options **rejected**, so reviews do
not re-litigate them. The directory listing is the index: there is no generated
listing and no `summary` frontmatter. `just check-adrs` validates the set, and
CI runs it.

## Numbering

Numbers run contiguously from `0001`, are permanent, and mean nothing beyond
identity. A new ADR takes the next free number. Nothing is ever renumbered.

## Status lives in the frontmatter, or nowhere

An ADR with no frontmatter is **accepted**. There is no exit from this
directory: a superseded decision stays readable, or it gets re-argued.

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

`## Consequence` is optional. `## Revisit trigger` is required and enforced.

## Where other facts go

This is one of four homes, and the narrowest. See
[`../../planning/README.md`](../../planning/README.md#where-a-fact-goes) for the
admission check that decides between code, an `INVARIANT:`-marked test, an ADR
here, and a deferred item in [`../../planning/deferred/`](../../planning/deferred/).
