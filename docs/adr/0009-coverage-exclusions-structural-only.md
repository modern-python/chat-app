# Coverage exclusions are structural only

The suite runs at `--cov-fail-under=100`, and exemptions are structural only:
`[tool.coverage.run] omit` for files the default pytest run never imports at
all, each carrying an inline reason in `pyproject.toml` where the path does not
explain itself, plus `exclude_also` for `if typing.TYPE_CHECKING:` blocks. No
`# pragma: no cover` appears in `app/`, `tests/` or `migrations/`. "Awkward to
reach" is not a warrant: where a branch looked untestable the answer was a
repository subclass that raises the condition the database would raise, which is
how both `DuplicateKeyError` recovery paths and both defensive `is None` guards
became executed code. Pragmas on unreachable-in-production guards were argued
for twice and refused, because an excluded branch is one nobody notices when it
stops being unreachable, and the coverage number then asserts something untrue
about what the tests exercise; tests written only to move the number were
removed for the same reason. `filterwarnings = ["error"]` enforces the companion
property, so a new warning fails a test rather than scrolling past.
