# Planning

The standing record for `chat-app`. The living truth about *what the system
does now* lives in the code itself and in its tests. This directory holds what
code and tests cannot: the decisions taken (especially the options rejected)
and the work deliberately not scheduled.

> **Local deviation.** This repo tracks the portable convention from
> [`lesnik512/planning-convention`](https://github.com/lesnik512/planning-convention)
> (applied version in `.convention-version`, beside this file), but **deviates
> from it** on six counts, listed under [Deviations](#deviations) below. The
> lean shape follows `modern-di`, which runs the same deviation; if it holds
> across both repos it goes upstream as convention 3.0.0.

## Quick path (start here)

**1. Write the spec in the PR body.**
[`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
carries the shape — why, design, non-goals, verification. There is no change
file to write and nothing to commit: the PR body *is* the spec, reviewed inline
with the diff. A trivial PR (typo, dep bump, formatter, mechanical rename) may
delete the template and ship a conventional-commit title.

**2. File what outlives the PR:**

- an alternative you **rejected** with reasoning → [`decisions/`](decisions/)
- work that is real but **not scheduled** → [`deferred/`](deferred/)

**3. Run `just check-planning` and `just check-links` before pushing.**

## Where a fact goes

Three homes, one owner each:

| Home | Holds |
|---|---|
| `app/` | anything readable from the module — the default |
| a named test | an **invariant**: must stay true, and a change could silently break it |
| `decisions/` | a rejected alternative, with the reasoning that would otherwise be re-litigated |

Before writing a line anywhere:

> Can an agent get this by reading `app/`? → **don't write it.**
> Would a wrong change here fail a test? → it belongs **in the test**, not in prose.
> Otherwise it does not get written.

**Prose about mechanism has no home. There is no file to add a paragraph to.**

This repo kept an `architecture/` directory of capability pages until 2026-08-22
and removed it. The pages had become a second telling of `decisions/` — the
twelve decision files referenced them zero times, while the pages re-narrated
the decisions at length — and one had gone silently wrong: `chats.md` still
described `chat_type` as a non-native enum months after #4 converted it to a
native Postgres enum, because the convention's promotion rule was a habit with
nothing enforcing it. A prose copy of a fact the code already owns goes stale in
the copy nobody edits. The absence of the directory is the mechanism.

`decisions/` and `INVARIANT:` docstrings inherit the same risk from the other
direction: nothing prunes a record once its call is settled. Keeping both lean
is a habit this repo owes them, not a one-time fix earned by deleting a
directory.

An invariant is written as a test whose name is the claim, with a docstring
opening `INVARIANT:` and a second paragraph naming **what breaks it**. That
second paragraph is design rationale — an anti-refactor warning — not a report
of what this one test happens to catch.

## Artifacts

- **[`decisions/<YYYY-MM-DD>-<slug>.md`](decisions/)** — one file per design
  decision taken, especially options *rejected*, each with a revisit trigger, so
  reviews don't re-litigate them. Frontmatter: `summary`, plus `superseded_by`
  once something supersedes it.
- **[`deferred/<YYYY-MM-DD>-<slug>.md`](deferred/)** — one file per open item,
  each **self-contained**: it inlines the evidence and reasoning needed to pick
  it up cold. Frontmatter: `summary`. A required `**Revisit trigger:**` section —
  an item with no trigger is abandoned, not deferred.
- **[`_templates/`](_templates/)** — `decision.md`, `deferred.md`.

### Location is status

Neither artifact carries a `status:` field. Where a file sits, and which keys it
has, is what its state means.

A **deferred item's presence in `deferred/` is its status**. When it resolves:

- **it ships** → delete the file. Its truth is now in the code and its tests.
- **it is declined** → move it to `decisions/`, so the refusal is on record.

A **decision is accepted unless it says otherwise**. There is no exit from
`decisions/` — a superseded decision stays readable, or it gets re-litigated —
so the one state worth recording is marked by adding `superseded_by: <slug>`,
which `just index` renders.

`date` and `slug` are derived from the file name and never repeated in
frontmatter. `summary` is one line; it is the only field the index renders.

## Index

The listing is **generated**, not maintained — run `just index` to print it:
deferred first (the open queue), then decisions, newest-first. The frontmatter
in each file is the single source of truth; there is no committed copy to drift.
`just check-planning` validates it, and `just check-links` validates every
relative Markdown link and heading anchor in the repo.

## Deviations

Against upstream convention 2.2.0:

1. `changes/`, `audits/` and `retros/` are removed; the per-change spec is the
   PR body.
2. `architecture/` is removed; there is no capability-page home and no promotion
   rule. Enforceable claims are `INVARIANT:`-marked tests; the ubiquitous
   language lives in [`../CLAUDE.md`](../CLAUDE.md)'s Vocabulary section.
3. `deferred.md` is a `deferred/` directory of indexed, trigger-bearing items.
4. Decision frontmatter drops `status` and `supersedes`.
5. `index.py` is edited to match that schema, and both `index.py` and `links.py`
   drop the canonical `# ruff: noqa: INP001` line — this repo ignores `INP`
   globally, so the directive is an unused `noqa` and fails `RUF100`.
6. There is no `lint-ci` recipe; CI inlines its lint steps, so `links.py` is
   wired into the workflow's `lint` job rather than a recipe.

Deviations 1–5 match `modern-di`'s practice. Applying a future convention
version will revert the edits in 5 — re-apply them.
