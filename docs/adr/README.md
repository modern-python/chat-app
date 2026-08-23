# Architecture decision records

One file per decision taken, especially the options **rejected**, so reviews do
not re-litigate them. `just check-adrs` validates the set; CI runs it.

The directory listing is the index. There is no generated listing and no
`summary` field: the number, the slug and the `# ` title already say what a file
is, and a fourth telling would be the copy nobody edits.

## Numbering is reading order, not chronology

Numbers run contiguously from `0001` and are permanent. They are assigned in
**dependency order**, so reading `0001` upward introduces the system in the
order its decisions build on each other: identity, then auth, then the error and
authorization vocabulary, then write patterns, then chat state, then events,
then testing policy.

A new ADR takes the next free number, which puts it at the end regardless of
where it belongs conceptually. That is the cost of permanence and it is
accepted: renumbering to preserve the reading order would break every existing
reference.

## Status lives in the frontmatter, or nowhere

An ADR with no frontmatter is **accepted**. There is no exit from this
directory: an ADR is never deleted or edited into reversal, because a superseded
decision that stays readable is one that does not get re-argued.

When a later ADR supersedes an earlier one, add to the earlier file:

```yaml
---
superseded_by: 0014-its-slug
---
```

`check.py` fails if that pointer does not name a real ADR.

## The admission test

All three must be true, or it is not an ADR:

1. **Hard to reverse.** Changing your mind later carries a real cost.
2. **Surprising without context.** A reader will look at the code and wonder why
   it was done this way.
3. **A real trade-off.** There were genuine alternatives and one was picked for
   specific reasons.

If a decision is easy to reverse, you will just reverse it. If it is not
surprising, nobody will wonder. If there was no alternative, there is nothing to
record beyond doing the obvious thing.

This is stricter than the stock format the `/domain-modeling` skill writes, which
treats rejected alternatives and consequences as optional and expects a body of
one to three sentences. Here they are the point of the file.

## Template

```md
# One-line capitalized title

**Decision:** What was decided, in a sentence.

What the code actually does, and the constraint that forced it.

## Rejected: <the obvious alternative>

Why it was not taken. Enough that a future explorer does not re-litigate it.

## Consequence

The non-obvious downstream effect, including what this deliberately leaves
uncovered.

## Revisit trigger

The concrete signal that should reopen this decision.
```

`## Rejected:` repeats once per alternative worth remembering. `## Consequence`
is optional. `## Revisit trigger` is **required** and `check.py` enforces it: a
decision with no trigger is never revisited, only rediscovered.

## Where other facts go

This directory is one of four homes, and the narrowest. See
[`../../planning/README.md`](../../planning/README.md#where-a-fact-goes) for the
admission check that decides between them: code, an `INVARIANT:`-marked test, an
ADR here, or a deferred item in [`../../planning/deferred/`](../../planning/deferred/).
