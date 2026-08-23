# Planning

The standing record for `chat-app`. The living truth about *what the system
does now* lives in the code itself and in its tests. This directory holds the
work deliberately not scheduled. The decisions taken, especially the options
rejected, live in [`../docs/adr/`](../docs/adr/) as numbered ADRs.

> **Local deviation.** This repo tracks the portable convention from
> [`lesnik512/planning-convention`](https://github.com/lesnik512/planning-convention)
> (applied version in `.convention-version`, beside this file), but **deviates
> from it** on seven counts, listed under [Deviations](#deviations) below. The
> lean shape follows `modern-di`, which runs deviations 1-5; if it holds across
> both repos it goes upstream as convention 3.0.0. Deviation 7, which moves
> decisions out of this directory entirely, runs here alone until it has been
> lived with.

## Quick path (start here)

**1. Write the spec in the PR body.**
[`.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
carries the shape — why, design, non-goals, verification. There is no change
file to write and nothing to commit: the PR body *is* the spec, reviewed inline
with the diff. A trivial PR (typo, dep bump, formatter, mechanical rename) may
delete the template and ship a conventional-commit title.

**2. File what outlives the PR:**

- an alternative you **rejected** with reasoning → [`../docs/adr/`](../docs/adr/)
- work that is real but **not scheduled** → [`deferred/`](deferred/)

**3. Run `just check-planning`, `just check-adrs` and `just check-links` before pushing.**

## Where a fact goes

Four homes, one owner each:

| Home | Holds |
|---|---|
| `app/` | anything readable from the module — the default |
| a named test | an **invariant**: must stay true, and a change could silently break it |
| `../docs/adr/` | a rejected alternative, with the reasoning that would otherwise be re-litigated |
| `deferred/` | real work, not scheduled, with a revisit trigger |

Before writing a line anywhere:

> Can an agent get this by reading `app/`? → **don't write it.**
> Would a wrong change here fail a test? → it belongs **in the test**, not in prose.
> Otherwise it does not get written.

**Prose about mechanism has no home. There is no file to add a paragraph to.**

This repo kept an `architecture/` directory of capability pages until 2026-08-22
and removed it. The pages had become a second telling of the decision
records — those files referenced them zero times, while the pages re-narrated the
decisions at length — and one had gone silently wrong: `chats.md` still
described `chat_type` as a non-native enum after #4 converted it to a native
Postgres enum, and nothing caught it, because the convention's promotion rule
was a habit with nothing enforcing it. A prose copy of a fact the code already
owns goes stale in the copy nobody edits. The absence of the directory is the
mechanism.

The ADRs and `INVARIANT:` docstrings inherit the same risk from the other
direction: nothing prunes a record once its call is settled. Keeping both lean
is a habit this repo owes them, not a one-time fix earned by deleting a
directory.

An invariant is written as a test whose name is the claim, with a docstring
opening `INVARIANT:` and a second paragraph naming **what breaks it**. That
second paragraph is design rationale — an anti-refactor warning — not a report
of what this one test happens to catch.

## Artifacts

- **[`deferred/<YYYY-MM-DD>-<slug>.md`](deferred/)** — one file per open item,
  each **self-contained**: it inlines the evidence and reasoning needed to pick
  it up cold. Frontmatter: `summary`. A required `**Revisit trigger:**` section —
  an item with no trigger is abandoned, not deferred.
- **[`_templates/`](_templates/)** — `deferred.md`.

Decisions are not an artifact of this directory. They are numbered ADRs in
[`../docs/adr/`](../docs/adr/), where [`../docs/adr/README.md`](../docs/adr/README.md)
carries their standard and template.

### Location is status

A deferred item carries no `status:` field. Where the file sits is what its
state means, and **its presence in `deferred/` is its status**. When it
resolves:

- **it ships** → delete the file. Its truth is now in the code and its tests.
- **it is declined** → write it up in [`../docs/adr/`](../docs/adr/), so the
  refusal is on record, and delete the deferred item.

`date` and `slug` are derived from the file name and never repeated in
frontmatter. `summary` is one line; it is the only field the index renders.

ADRs run the same principle with a different mechanism: no frontmatter means
accepted, and `superseded_by` is the one state worth recording. See
[`../docs/adr/README.md`](../docs/adr/README.md#status-lives-in-the-frontmatter-or-nowhere).

## Index

The listing is **generated**, not maintained — run `just index` to print the
deferred queue, newest-first. The frontmatter in each file is the single source
of truth; there is no committed copy to drift. `just check-planning` validates
it, and `just check-links` validates every relative Markdown link and heading
anchor in the repo.

ADRs have no generated listing: they are numbered, so the directory listing is
the index. `just check-adrs` validates their numbering, naming and revisit
triggers.

## Deviations

Against upstream convention 2.2.0:

1. `changes/`, `audits/` and `retros/` are removed; the per-change spec is the
   PR body.
2. `architecture/` is removed; there is no capability-page home and no promotion
   rule. Enforceable claims are `INVARIANT:`-marked tests; the ubiquitous
   language lives in [`../CONTEXT.md`](../CONTEXT.md).
3. `deferred.md` is a `deferred/` directory of indexed, trigger-bearing items.
4. Decision frontmatter drops `status` and `supersedes`. Largely subsumed by 7:
   decisions are no longer a `planning/` artifact at all.
5. `index.py` is edited to match that schema, and both `index.py` and `links.py`
   drop the canonical `# ruff: noqa: INP001` line — this repo ignores `INP`
   globally, so the directive is an unused `noqa` and fails `RUF100`.
6. There is no `lint-ci` recipe; CI inlines its lint steps, so `links.py` runs
   as a step in the workflow's `lint` job rather than via a recipe CI calls.
   `just check-links` exists for running it locally.
7. `decisions/` is removed. Design decisions are numbered ADRs in
   [`../docs/adr/`](../docs/adr/), validated by `docs/adr/check.py`, and carry no
   `summary` frontmatter: the number, the slug and the title already identify the
   file. `index.py` indexes the deferred queue alone.

Deviations 1–5 match `modern-di`'s practice; deviation 7 does not yet. Applying a future convention
version runs upstream's `APPLY.md`, which copies `index.py` and `links.py` over
any local version by design — that reverts the edits in 5, so re-apply them
afterwards.
