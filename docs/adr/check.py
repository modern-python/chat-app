"""Validate the ADR set: numbering, naming, revisit triggers, supersession pointers.

Run via ``just check-adrs``. Globs ``docs/adr/*.md`` and reports every violation
at once rather than failing on the first.

ADRs carry no ``summary`` frontmatter: the number, the slug and the ``# `` title
already say what the file is, and a fourth telling would be the copy nobody
edits. Frontmatter appears only on a superseded ADR, so *no frontmatter* means
accepted.

Numbers must be contiguous from ``0001``. An ADR is never deleted — it is
superseded — so a gap is a mistake worth failing on, not a deliberate state.
"""

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).parent
ADR_RE = re.compile(r"^(?P<number>\d{4})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$")
REVISIT_HEADING = "## Revisit trigger"


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse a single-line-scalar YAML frontmatter block into a dict."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line[:1] in (" ", "\t"):
            continue
        key, sep, value = line.partition(": ")
        if not sep:
            continue
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def adr_paths(root: pathlib.Path) -> list[pathlib.Path]:
    """Every ADR file, sorted by name; README and underscore-prefixed files are not ADRs."""
    return [path for path in sorted(root.glob("*.md")) if path.name != "README.md" and not path.name.startswith("_")]


def _check_numbering(paths: list[pathlib.Path], violations: list[str]) -> None:
    """Require each name to be `NNNN-slug.md`, numbered contiguously from 0001."""
    numbers: dict[int, str] = {}
    for path in paths:
        match = ADR_RE.match(path.stem)
        if match is None:
            violations.append(f"{path.name}: file name is not 'NNNN-slug.md' with a lowercase hyphenated slug")
            continue
        number = int(match.group("number"))
        if number in numbers:
            violations.append(f"{path.name}: number {number:04d} is already taken by {numbers[number]}")
            continue
        numbers[number] = path.name
    expected = set(range(1, len(numbers) + 1))
    violations.extend(
        f"ADR {number:04d} is missing — numbers run contiguously from 0001" for number in expected - numbers.keys()
    )


def _check_body(path: pathlib.Path, stems: set[str], violations: list[str]) -> None:
    """Require a revisit trigger, and a `superseded_by` that names a real ADR."""
    text = path.read_text(encoding="utf-8")
    if REVISIT_HEADING not in text:
        violations.append(
            f"{path.name}: no '{REVISIT_HEADING}' section — a decision with no trigger is never revisited"
        )
    superseded_by = parse_frontmatter(text).get("superseded_by")
    if superseded_by is None:
        return
    if superseded_by == path.stem:
        violations.append(f"{path.name}: superseded_by points at itself")
    elif superseded_by not in stems:
        violations.append(f"{path.name}: superseded_by '{superseded_by}' does not name an ADR in docs/adr/")


def check(root: pathlib.Path) -> list[str]:
    """Validate every ADR; return the list of violation strings."""
    violations: list[str] = []
    paths = adr_paths(root)
    _check_numbering(paths, violations)
    stems = {path.stem for path in paths}
    for path in paths:
        _check_body(path, stems, violations)
    return violations


def main(root: pathlib.Path | None = None) -> int:
    """Report every violation on stderr, or confirm the set is clean on stdout."""
    violations = check(ROOT if root is None else root)
    if violations:
        sys.stderr.write(f"adr: {len(violations)} violation(s)\n")
        for violation in violations:
            sys.stderr.write(f"  - {violation}\n")
        return 1
    sys.stdout.write("adr: OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
