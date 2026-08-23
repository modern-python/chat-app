# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **single-context**: one glossary and one decision log, both at the root. There is no `CONTEXT-MAP.md`, no per-context `CONTEXT.md`, and no context-scoped ADR directory.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root: the glossary, and nothing but the glossary.
- **`docs/adr/`**: the ADRs that touch the area you're about to work in. `docs/adr/README.md` carries the local standard, which is stricter than the stock ADR format: rejected alternatives and a revisit trigger are required, not optional.

If either doesn't exist yet, **proceed silently**. Don't flag its absence; don't suggest creating it upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-sequence-ids-not-snowflakes.md
│       └── 0002-cookie-auth-not-bearer.md
├── app/
└── tests/
```

ADR numbers are permanent and assigned in dependency order, so reading from `0001` upward introduces the system in the order its decisions build on each other. A new ADR takes the next free number.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (upsert via duplicate-key recovery), but worth reopening because…_
