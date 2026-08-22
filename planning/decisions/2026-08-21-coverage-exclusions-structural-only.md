---
summary: Coverage exclusions are reserved for code pytest structurally cannot execute; unreachable-in-production branches are tested through repository seams instead.
---

# Coverage exclusions are structural only

The suite runs at `--cov-fail-under=100`. Two mechanisms can exempt code, and
each has a narrow warrant:

- `[tool.coverage.run] omit` lists `migrations/*`, `app/api/__main__.py` and
  `planning/index.py` — files pytest never imports at all.
- `# pragma: no cover` is not used anywhere in `app/`, `tests/` or
  `migrations/`.

"Awkward to reach" is not a warrant. Where a branch looked untestable, the
answer was a repository subclass that raises the condition the database would
raise. That is how both `DuplicateKeyError` recovery paths and both defensive
`is None` guards became executed code.

`filterwarnings = ["error"]` enforces the companion property: the suite runs at
zero warnings, and a new warning fails a test rather than scrolling past.

## Rejected: pragmas on unreachable-in-production guards

Argued for twice during implementation, on the grounds that the guards cannot
fire while the unique constraint holds. Rejected because an excluded branch is
one nobody notices when it stops being unreachable, and because the coverage
number then asserts something untrue about what the tests exercise. The two
guards in question were reachable through a seam the tests already owned.

## Rejected: tests written only to move the number

Also seen and removed: an `assert __name__ != "__main__"` that could not fail,
and an `isinstance` check against a function whose body constructs that type.
The gate exists to make untested code visible; satisfying it with assertions
that cannot fail defeats it more thoroughly than a lower number would.

## Consequence

Adding genuinely unexecutable code requires an `omit` entry with a stated
reason, reviewed as a decision rather than applied inline.

## Revisit trigger

A dependency that emits an unfixable warning, or platform-specific code paths
that cannot run in CI.
